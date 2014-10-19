from locust import HttpLocust, TaskSet, task
from pyquery import PyQuery

class LoggedInTeam(TaskSet):

    users = ['team701', 'team702', 'team703', 'team704', 'team705', 'team706', 'team707', 'team708', 'team709', 'team710', 'team711', 'team712', 'team713', 'team801', 'team802', 'team803', 'team804', 'team805', 'team806', 'team807', 'team808', 'team809', 'team810', 'team811', 'team812', 'team813', 'team814', 'team815', 'team816', 'team817', 'team818', 'team819', 'team820', 'team821', 'team822', 'team823', 'team824', 'team825', 'team501', 'team502', 'team503', 'team504', 'team505', 'team506', 'team507', 'team508', 'team509', 'team510', 'team511', 'team512', 'team513', 'team514', 'team515', 'team516', 'team517', 'team518', 'team519', 'team520', 'team521', 'team522', 'team523', 'team524', 'team525', 'team401', 'team402', 'team403', 'team404', 'team405', 'team406', 'team301', 'team302', 'team303', 'team304', 'team305', 'team306', 'team307', 'team308', 'team309', 'team310', 'team601', 'team602', 'team603', 'team604', 'team605', 'team606', 'team607', 'team608', 'team609', 'team610', 'team611', 'team612', 'team613', 'team614', 'team615', 'team616', 'team617', 'team618', 'team619', 'team620', 'team621', 'team201', 'team202', 'team203', 'team204', 'team205', 'team206', 'team207', 'team208', 'team209', 'team210', 'team211', 'team212', 'team213', 'team901', 'team902', 'team903', 'team904', 'team905', 'team906', 'team907', 'team908', 'team909', 'team910', 'team911', 'team912', 'team913', 'team914', 'team915', 'team916', 'team917', 'team918', 'team919', 'team920', 'team921', 'team922', 'team923', 'team924', 'team925', 'team926', 'team927', 'team101', 'team102', 'team103', 'team104', 'team105', 'team106', 'team107', 'team108', 'team109', 'team110', 'team111', 'team112', 'team113', 'team114']

    def on_start(self):
        r = self.client.get("/Login/login.php", verify=False)
        pq = PyQuery(r.content, parser="html")
        session = pq.find("input[name=SESSION_NAME]")[0].value

        team = LoggedInTeam.users.pop()

        r = self.client.post("/Login/login.php", {"username":team, "password":team, "SESSION_NAME":session}, verify = False)

        self.team = team
        self.session = session     

        r = self.client.get("/Team/iSubmit.php?SESSION_NAME=%s" % self.session, verify=False)
        r = self.client.get("/Team/iSendClarification.php?SESSION_NAME=%s" % self.session, verify=False)
        r = self.client.get("/Team/iViewRuns.php?SESSION_NAME=%s" % self.session, verify=False)
        r = self.client.get("/Team/iViewClarifications.php?SESSION_NAME=%s" % self.session, verify=False)
        r = self.client.get("/Team/iScoreboard.php?SESSION_NAME=%s" % self.session, verify=False)

    #@task(10)
    #def scoreboard(self):
    #    r = self.client.get("/Team/iScoreBoard.php?SESSION_NAME=%s" % self.session, verify=False)


    @task(1)
    def getClars(self):
        r = self.client.post("/Team/getClars.php", {"SESSION_NAME": self.session}, verify=False)

    @task(1)
    def getRuns(self):
        r = self.client.post("/Team/getRuns.php", {"SESSION_NAME": self.session}, verify=False)

    @task(5)
    def getClock(self):
        r = self.client.post("/Team/getClock.php", {"SESSION_NAME": self.session}, verify=False)


class WebsiteUser(HttpLocust):
    host = "https://contest-server.cs.uchicago.edu/pc2team"
    task_set = LoggedInTeam
    min_wait = 1000
    max_wait = 1200
