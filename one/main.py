import csv
import os
import random
import time


import json,atexit
import humanize
import uuid

import requests

import urllib.parse
from tinydb import TinyDB

class Instagramify:
    def __init__(self):
        self.posts_data = []
        self.file_name = time.time()
        atexit.register(self.on_graceful_exit)

        self.user_agent = "Instagram 4.1.1 Android (11/1.5.0; 285; 800x1280; samsung; GT-N7000; GT-N7000; smdkc210; en_US)"
        self.guid = str(uuid.uuid1())

        self.login_url = "https://i.instagram.com/api/v1/accounts/login/"
        self.posts_link = 'https://i.instagram.com/api/v1/feed/user/'
        self.comments_link = 'https://www.instagram.com/graphql/query/?query_hash=bc3296d1ce80a24b1b6e40b1e72903f5&variables={}'

        self.db =  TinyDB('{}.json'.format(self.file_name))
        self.loop_targets()


    def loop_targets(self):
        with open('targets.txt', 'r') as f:
            links = [line.strip() for line in f]
        f.close()
        links = list(filter(None, links))
        for (i,link) in enumerate(links):
            print("We starting with #{}",format(i+1))
            self.current_url = link
            self.login(self.current_url)
            
    def login(self,link,is_rate=False):
        self.session = requests.Session()
        self.session.headers.update(
            {'User-Agent': self.user_agent, 'Content-Type': 'application/x-www-form-urlencoded', })
        text_accounts = open("accounts.txt",'r')
        accounts = [line.strip() for line in text_accounts]
        accounts = list(filter(None, accounts))
        random_account = random.choices(accounts)[0]

        username = random_account.split(":")[0]
        password = random_account.split(":")[1]
        print("Trying with ID:{}".format(username))
        payload = 'password={}&username={}&device_id={}'.format(password,username,self.guid)
        login_response = self.session.post(self.login_url, payload)
        login_response = login_response.json()
        if login_response['logged_in_user']:
            print("Logged in with ID:{}".format(username))
            self.basic_information(link)
        else:
            print("Something Went Wrong while logging in.... USER:{}".format(username))
            exit()

    def basic_information(self, link):
        print("Getting Basic Public Information")
        r = self.session.get("{}?__a=1".format(link))
        r = r.json()['graphql']['user']

        self.user_data = {
            "followed": humanize.intcomma(r['edge_followed_by']['count']),
            "following": humanize.intcomma(r['edge_follow']['count']),
            "posts": humanize.intcomma(r['edge_owner_to_timeline_media']['count']),
            "is_verified": r['is_verified'],
            "full_name": r['full_name'],
            "user_id": r['id'],
            "username": r['username'],
            "link": link
        }
        users = self.db.table("users")
        users.insert(self.user_data)
        print(self.user_data)
        print("Basic Information Done")
        self.start_post_fetch(self.user_data)

    def start_post_fetch(self, data):
        num_results = 0
        self.posts_data = []
        # GET first 18
        r = self.session.get(self.posts_link + data['user_id']).json()
        num_result = r['num_results']
        next_id = None
        if num_result > 1:
            if "next_max_id"  in r:
                next_id = r['next_max_id']
            
            self.posts_data.append(self.fetch_post_data(r))
            num_results += num_result
            while num_results < 100 and next_id is not None:
                # GET 82
                r_2 = self.session.get(self.posts_link + data['user_id'] + "/?max_id=" + next_id).json()
                next_id = r_2['next_max_id']
                num_result = r_2['num_results']
                self.posts_data.append(self.fetch_post_data(r_2))
                num_results += num_result
                print(num_results)
            self.posts_data = [x for x in self.posts_data if x is not None]
            self.posts_data = self.posts_data[:100]
            print(len(self.posts_data))
            self.fetch_post_comments()

    def fetch_post_data(self, json_response):
        posts = self.db.table("posts")
        for i in json_response['items']:
            if i is not None:
                caption = "No caption detected"
                if i['caption']:
                    caption = i['caption']['text']
                post_object = {
                    "id": i['id'],
                    "likes": i['like_count'],
                    "comments_count": i['comment_count'],
                    "code": i['code'],
                    "caption": caption,
                    "comments": [],
                    "user": self.user_data,

                }
                self.posts_data.append(post_object)
                posts.insert(post_object)


    def fetch_post_comments(self, ):
        
        for (post_id,i) in enumerate(self.posts_data):
            try:
                variable = self.comments_object_convertor(i['code'])
                r = self.session.get(self.comments_link.format(variable)).json()
                if r['status'] != "fail":
                    comments_we_have = 0
                    page_info_data = r['data']['shortcode_media']['edge_media_to_parent_comment']
                    count = len(page_info_data['edges'])
                    
                    is_has_more = page_info_data['page_info']['has_next_page']
                    is_has_more_hash = False
                    if is_has_more and count != 0:
                        is_has_more_hash = page_info_data['page_info']['end_cursor']
                    print("Post #{} Comments Count {}".format(i['code'],count))
                    print("Post #{} has more Comments? {}".format(i['code'],is_has_more))
                    
                    for comment in page_info_data['edges']:
                        self.comments_appender(comment,i)
                        comments_we_have +=1
                    print("We have {} comments of {} : {} #{}".format(comments_we_have,count+comments_we_have, i['code'],post_id))
                    while is_has_more and count != 0:
                        
                        time.sleep(3)
                        variable = self.comments_object_convertor(i['code'], is_has_more_hash)
                        print(variable)
                        r = self.session.get(self.comments_link.format(variable)).json()
                        page_info_data = r['data']['shortcode_media']['edge_media_to_parent_comment']
                        count = len(page_info_data['edges'])
                        is_has_more = page_info_data['page_info']['has_next_page']
                        is_has_more_hash = page_info_data['page_info']['end_cursor']
                        print("Post #{} Comments Count {}".format(i['code'],count))
                        print("Post #{} has more Comments?".format(i['code']), is_has_more)
                        for comment in page_info_data['edges']:
                            self.comments_appender(comment,i)
                            comments_we_have +=1
                        print("We have {} comments of {} : {} #{}".format(comments_we_have,count+comments_we_have, i['code'],post_id))
                        time.sleep(3)
                    time.sleep(3)
                else:
                    print("ERROR: from INSTAGRAM API or Account limited... trying other account")
                    self.login(self.current_url,is_rate=True)
            except Exception as e:
                print(i)
                print("ERROR: ", e)
                print("ERROR: from INSTAGRAM API or Account limited..... trying to Logging in with other account")
                self.login(self.current_url,is_rate=True)
                continue
        print("Fetching Comments of Post #{}".format(post_id+1))
        self.save_results()


    def comments_appender(self,comment,i):
    
        comments = self.db.table("comments")
        is_verified = "No"
        if comment['node']['owner']['is_verified'] == True:
            is_verified = "YES"

        comment_object = {
                            "comment_id": comment['node']['id'],
                            "user_commented": comment['node']['owner']['username'],
                            "user_link": 'https://instagram.com/{}'.format(comment['node']['owner']['username']),
                            "is_verified": is_verified,
                            "comment": comment['node']['text']
                        }
        i['comments'].append(comment_object)
        comments.insert(comment_object)

       
        
    def comments_object_convertor(self, code, after=None):
        if after:
            variable = {"shortcode": code, "first": 50, "after": after}
        else:
            variable = {"shortcode": code, "first": 50}
        j = json.dumps(variable)
        return urllib.parse.quote_plus(j)

    def is_rate_limited(self, response):
        if response['status'] == "fail" or response['message'] == "feedback_required":
            print("This account is limited. trying another account....")

    def save_results(self):
        with open('{}.csv'.format(self.file_name), 'a', newline='', encoding="utf-8-sig",) as Saver:
            headerList = ['Username', 'Link', 'Posts Count', 'Following','Followers', 'Caption',"Likes","User Commended","Comment","Commenter Link","Blue Badge"]
            dw = csv.DictWriter(Saver, delimiter=',', fieldnames=headerList)
            dw.writeheader()
            results_writer = csv.writer(Saver)
            for p in self.posts_data:
                    try:

                        for c in p['comments']:
                            if p['user']:
                                results_writer.writerow(
                                    [p['user']['username'], p['user']['link'], p['user']['posts'], p['user']['following'],
                                     p['user']['followed'], p['caption'], p['likes'], c['user_commented'], c['comment'], c['user_link'],
                                     c['is_verified']])
                    except Exception as e:
                        print("ERROR: Saving file error, ",e)
                        continue
            self.posts_data = []
        Saver.close()
        
    def on_graceful_exit(self):
        # Check if already saved?
        isExisted = os.path.exists('{}.csv'.format(self.file_name)) 
        if isExisted:
            print("File Saved Successfully")
        else:
            if len(self.posts_data) > 0:
                self.save_results()
                print("File Saved Successfully")
            else:
                print("Nothing to be saved")


if __name__ == '__main__':
    app = Instagramify()
