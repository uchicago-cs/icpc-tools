from locust import HttpLocust, TaskSet, task
from pyquery import PyQuery
import yaml

with open("config.yaml") as f:
    config = yaml.load(f)

users = config["teams"]

freq_scoreboard = config["frequencies"]["scoreboard"]
freq_run = config["frequencies"]["run"]
freq_clar = config["frequencies"]["clar"]
freq_logout = config["frequencies"]["logout"]

freq_polling = 600 - freq_scoreboard - freq_run - freq_clar - freq_logout

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

        self.__login(username, password)

        self.username = username
        self.password = password


    def do_polling_requests(self):
        r = self.client.post("/Team/getClock.php", {"SESSION_NAME": self.session}, verify=False)
        self.runclar_countdown -= 1
        if self.runclar_countdown == 0:
            r = self.client.post("/Team/getClars.php", {"SESSION_NAME": self.session}, verify=False)
            r = self.client.post("/Team/getRuns.php", {"SESSION_NAME": self.session}, verify=False)
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
        # TODO

    @task(freq_clar)
    def submit_clar(self):
        self.do_polling_requests()
        # TODO

    @task(freq_polling)
    def poll(self):
        self.do_polling_requests()


class WebsiteUser(HttpLocust):
    host = "https://contest-server.cs.uchicago.edu/pc2team"
    task_set = LoggedInTeam
    min_wait = 900
    max_wait = 1100
