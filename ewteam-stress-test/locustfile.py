from locust import HttpLocust, TaskSet, task
from pyquery import PyQuery
import yaml
import urllib
import random

with open("config.yaml") as f:
    config = yaml.load(f)

url = config["url"]

users = config["teams"]

freq_scoreboard = config["frequencies"]["scoreboard"]
freq_run = config["frequencies"]["run"]
freq_clar = config["frequencies"]["clar"]
freq_logout = config["frequencies"]["logout"]

freq_polling = 600 - freq_scoreboard - freq_run - freq_clar - freq_logout

languages = config["languages"]
problems = config["problems"]
nproblems = len(problems)

max_runs = config["max_runs"]
max_clars = config["max_clars"]
max_tries = config["max_tries"]

num_runs = 0
num_clars = 0

correct_submissions = {}
incorrect_submissions = {}

for k,v in config["correct_submissions"].items():
    with open(v) as f:
        correct_submissions[k] = (v, f.read())

for k,v in config["incorrect_submissions"].items():
    with open(v) as f:
        incorrect_submissions[k] = (v, f.read())


class LoggedInTeam(TaskSet):

    def __login(self, username, password):
        r = self.client.get("/Login/login.php", verify=False)
        pq = PyQuery(r.content, parser="html")
        session = pq.find("input[name=SESSION_NAME]")[0].value

        r = self.client.post("/Login/login.php", {"username":username, "password":password, "SESSION_NAME":session}, verify = False)

        self.session = session     
        self.runclar_countdown = 5

        # Fetch iframes in main page
        r = self.client.get("/Team/iSubmit.php?SESSION_NAME=%s" % self.session, 
                            name="/Team/iSubmit.php", verify=False)
        r = self.client.get("/Team/iSendClarification.php?SESSION_NAME=%s" % self.session,
                            name="/Team/iSendClarification.php", verify=False)
        r = self.client.get("/Team/iViewRuns.php?SESSION_NAME=%s" % self.session,
                            name="/Team/iViewRuns.php", verify=False)
        r = self.client.get("/Team/iViewClarifications.php?SESSION_NAME=%s" % self.session,
                            name="/Team/iViewClarifications.php", verify=False)
        r = self.client.get("/Team/iScoreBoard.php?SESSION_NAME=%s" % self.session,
                            name="/Team/iScoreBoard.php", verify=False)



    def __logout(self):
        r = self.client.post("/Team/logout.php?SESSION_NAME=%s" % self.session, 
                             name="/Team/logout.php", verify = False)
        self.session = None

    def on_start(self):
        username, password = users.popitem()

        self.nproblems_solved = 0
        self.current_problem = 0
        
        # Set the number of tries it will take to solve the problem
        # We assume the number of tries increases as the team moves on
        # to harder problems
        problems_per_numtry = nproblems / (max_tries + 1)
        n = 0
        cur_numtry = 1
        self.tries = {}
        for problem in problems:
            if n > problems_per_numtry:
                cur_numtry += 1
                n = 0
            self.tries[problem] = cur_numtry
            n += 1

        # Language of choice for this user
        self.language = random.choice(languages)

        self.__login(username, password)

        self.username = username
        self.password = password


    def do_polling_requests(self):
        r = self.client.post("/Team/getClock.php", {"SESSION_NAME": self.session}, verify=False)
        self.runclar_countdown -= 1
        if self.runclar_countdown == 0:
            r = self.client.post("/Team/getClars.php", {"SESSION_NAME": self.session}, verify=False)
            r = self.client.post("/Team/getRuns.php", {"SESSION_NAME": self.session}, verify=False)
            r = self.client.post("/Team/verifyRunSubmission.php", {"SESSION_NAME": self.session}, verify=False)
            r = self.client.post("/Team/VerifyClarificationSubmission.php", {"SESSION_NAME": self.session}, verify=False)
            self.runclar_countdown = 5

    @task(freq_logout)
    def logout_login(self):
        self.__logout()
        self.__login(self.username, self.password)

    @task(freq_scoreboard)
    def scoreboard(self):
        self.do_polling_requests()
        r = self.client.get("/Team/iScoreBoard.php?SESSION_NAME=%s" % self.session,
                            name="/Team/iScoreBoard.php", verify=False)

    @task(freq_run)
    def submit_run(self):
        self.do_polling_requests()
        
        global num_runs

        if num_runs < max_runs and self.nproblems_solved < nproblems:
            problem_name = problems[self.current_problem]
            tries_left = self.tries[problem_name]

            if tries_left == 1:
                filename, submission = correct_submissions[self.language]
            else:
                filename, submission = incorrect_submissions[self.language]            

            files = {'file': (filename, submission, 'text/plain', {})}

            data = {"probs": urllib.quote_plus(problem_name), 
                    "lang": urllib.quote_plus(self.language), 
                    "SESSION_NAME": self.session}

            r = self.client.post("/Team/submitProblem.php", data=data, files=files, verify=False)

            self.tries[problem_name] -= 1
            num_runs += 1

            if self.tries[problem_name] == 0:
                self.current_problem += 1
                self.nproblems_solved += 1

            if self.nproblems_solved == nproblems:
                print "%s has submitted all its runs" % self.username

            if num_runs == max_runs:
                print "The maximum number of runs (%i) has been reached" % max_runs

    @task(freq_clar)
    def submit_clar(self):
        self.do_polling_requests()

        global num_clars

        if num_clars < max_clars and self.nproblems_solved < nproblems:

            problem_name = problems[self.current_problem]

            data = {"clarProbs": urllib.quote_plus(problem_name), 
                    "clarificationTextArea": "Clarification request from %s" % self.username, 
                    "SESSION_NAME": self.session}

            r = self.client.post("/Team/submitClarification.php", data=data, verify=False)

            num_clars += 1

    @task(freq_polling)
    def poll(self):
        self.do_polling_requests()


class WebsiteUser(HttpLocust):
    host = url
    task_set = LoggedInTeam
    min_wait = 900
    max_wait = 1100
