import csv
import random
import time


import humanize
import uuid
from humanize.number import intcomma

import requests


from tinydb import TinyDB,Query


class Commentify:
    def __init__(self):
        self.file_name = time.time()
        self.user_agent = "Instagram 4.1.1 Android (11/1.5.0; 285; 800x1280; samsung; GT-N7000; GT-N7000; smdkc210; en_US)"
        self.guid = str(uuid.uuid1())

        self.login_url = "https://i.instagram.com/api/v1/accounts/login/"
        self.followers_url = "https://i.instagram.com/api/v1/friendships/{}/followers/?count={}&search_surface=follow_list_page"
        print("Please, Put JSON file in this folder. and paste it's name in the input field")
        db_path = input("JSON file name (EX:16666666.json): ")
        self.db = TinyDB(db_path)
        self.commenters_db = TinyDB("{}.json".format(self.file_name))

        self.commenters = []

        self.SearchInDB = Query()
        self.login()
        
     
    def login(self):
        self.session = requests.Session()
        self.session.headers.update(
            {'User-Agent': self.user_agent, 'Content-Type': 'application/x-www-form-urlencoded'})
        text_accounts = open("accounts.txt",'r')
        accounts = [line.strip() for line in text_accounts]
        accounts = list(filter(None, accounts))
        random_account = random.choices(accounts)[0]

        username = random_account.split(":")[0]
        password = random_account.split(":")[1]
        print("Trying with ID:{}".format(username))
        payload = 'password={}&username={}&device_id={}'.format(password.strip(),username.strip(),self.guid)
        login_response = self.session.post(self.login_url, payload)
        login_response = login_response.json()
        if login_response['logged_in_user']:
            print("Logged in with ID:{}".format(username))
            self.get_comments()
        else:
            print("Something Went Wrong while logging in.... USER:{}".format(username))
            exit()

    def get_comments(self):
        all_comments = self.db.table("comments").all()
        if len(all_comments) > 0:
            print("We have got {} comment to look into it!".format(humanize.intcomma(len(all_comments))))
            for i,comment in enumerate(all_comments):
                self.get_commenter_public_info(comment,i)
                
            print("Actual Number of Commenters (Remove Duplicates) #{}".format(len(self.commenters)))
            self.get_followers_info()
            

        else:
            print("Whops! we did not see any comments")
            exit()


    def get_commenter_public_info(self,comment,i):
        try:
            
            is_exitsted = self.commenters_db.table("commenters").search(self.SearchInDB.username == comment['user_commented'])
            if len(is_exitsted) == 0:
                r = self.session.get("https://instagram.com/{}?__a=1".format(comment['user_commented']))
                r = r.json()['graphql']['user']
                is_verified = "No"
                if r['is_verified'] == True:
                    is_verified = "Yes"
                commenter = {
                    "followedBy": humanize.intcomma(r['edge_followed_by']['count']),
                    "following_count": humanize.intcomma(r['edge_follow']['count']),
                    "posts": humanize.intcomma(r['edge_owner_to_timeline_media']['count']),
                    "is_verified": is_verified,
                    "full_name": r['full_name'],
                    "user_id": r['id'],
                    "username": r['username'],
                    "followers":[],
                    "is_private":r['is_private'],
                    "link":"https://instagram.com/{}".format(r['username'])
                }
                self.commenters_db.table("commenters").insert(commenter)
                self.commenters.append(commenter)
                print("Commenter #{} Public Info Ready.".format(i+1))
                time.sleep(1)
            else:
                print("Skipping commenter due to duplicate")
        except KeyError as e:
            print("ERROR: Key error on {}".format(comment['user_commented']))
            
        

    def get_followers_info(self):
            
            for (i,commenter) in enumerate(self.commenters):
                    try:
                        if commenter['is_private'] == False:
                            print("Commenter #{} of {}".format(i+1, intcomma(len(self.commenters))))
                            followers_list = self.session.get(self.followers_url.format(commenter['user_id'],commenter['following_count'])).json()
                            data = followers_list['users']
                            count_following_from_api = len(data)
                            print("Commenter with id: {} followers #{}".format(commenter['username'],humanize.intcomma(count_following_from_api)))
                            for f in data:
                                is_verified = "No"
                                if f['is_verified'] == True:
                                    is_verified = "Yes"
                                follower = {
                                "username":f['username'],
                                "link":"https://instagram/{}".format(f['username']),
                                "is_verified":is_verified,
                                "origin_user":commenter['username']
                                }
                                commenter['followers'].append(follower)
                                self.commenters_db.table("followers").insert(follower)
                            time.sleep(3)
                        else:
                            print("Skipping {} due to private account".format(commenter['username']))
                        
                    except Exception as e:
                        print(e)
                        print("ERROR: Something wrong ", e)
                        print("Located ERROR:", i)
                        continue
            self.save_results()

    def save_results(self):
        with open('{}.csv'.format(self.file_name), 'a', newline='', encoding="utf-8-sig") as Saver:
            headerList = ['Username', 'Link', 'Posts Count', 'Followers','Following', 'Follower Username',"Follower Link","Blue Badge"]
            dw = csv.DictWriter(Saver, delimiter=',', fieldnames=headerList)
            dw.writeheader()
            results_writer = csv.writer(Saver)
            for commenter in self.commenters:
                    try:

                        for f in commenter['followers']:
                            if commenter['user_id']:
                                results_writer.writerow(
                                    [commenter['username'],commenter['link'],  commenter['posts'], commenter['followedBy'],
                                     commenter['following_count'], f['username'], f['link'],f['is_verified']])
                    except Exception as e:
                        print("ERROR: Saving file error, ",e)
                        continue
        Saver.close()   
        self.commenters = []      
if __name__ == '__main__':
    app = Commentify()
        
