#!/usr/bin/python

# PC^2 scoreboard publishing script
#
# See README for instructions
#
# (c) 2014, Borja Sotomayor

from argparse import ArgumentParser, FileType
from pprint import pprint as pp
from datetime import datetime
import os
import os.path
import stat
import subprocess
import socket
import time
import re
import urllib2

try:
    import yaml
    import paramiko
except ImportError, ie:
    print "Your system is missing a required software library to run this script."
    print "Try running the following:"
    print 
    print "    pip install --user PyYAML paramiko"
    print 
    exit(1)

# Constants

# To avoid users from shooting themselves in the foot,
# the minimum interval between scoreboard intervals is
# 10 seconds. Change this at your own peril.
MIN_UPDATE_INTERVAL = 10

# When to start warning that the scoreboard will be frozen
FREEZE_WARNING_MINUTES = 10

# Globals
verbose = False


def log(msg):
    print "[%s] %s" % (now_str(), msg)

def vlog(msg):
    if verbose:
        log(msg)

def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def td_str(td):
    s = int(td.total_seconds())

    hours = s / 3600
    s = s % 3600
    minutes = s / 60
    seconds = s % 60

    return "%i hour(s), %i minutes(s), %i seconds(s)" % (hours, minutes, seconds)

def print_http_response(response):
    print "HTTP Status Code: %i" % response.status_code
    print
    print "HTTP Response"
    print "-------------"
    pp(response.headers.items())
    print
    pp(response.text)

def connect_to_server(server, username, path):
    ntries = 3
    reconnect = 5

    while ntries > 0:
        success = True
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
            ssh.connect(hostname=server, username=username)
            sftp = ssh.open_sftp()
        except paramiko.AuthenticationException, ae:
            log("ERROR: Authentication error connection to %s" % server)
            success = False
        except paramiko.SSHException, sshe:
            log("ERROR: SSH error when connecting to %s" % server)
            success = False
        except socket.error:
            log("ERROR: Network error when connecting to %s" % server)
            success = False

        if not success:
            ntries -= 1
            if ntries == 0:
                log("ERROR: Unable to connect to %s. Giving up." % server)
                exit(1)
            log("Trying to reconnect to %s in %i seconds (%i tries left)" % (server, reconnect, ntries))
            time.sleep(reconnect)
            reconnect = 2*reconnect
        else:
            break
            
    try:
        stdin, stdout, stderr = ssh.exec_command('stat %s' % path)
        so = stdout.read()
        se = stderr.read()

        if len(se) > 0:
            print "ERROR: Error when trying to read remote web directory %s" % path
            print
            print "stderr: %s" % (se)
            exit(1)
    except paramiko.SSHException, sshe:
        print "ERROR: SSH error when connecting to %s (couldn't stat remote directory)" % server
        exit(1)        

    try:
        sftp.chdir(path)
    except IOError, ioe:
        print "ERROR: Could not set SFTP client to directory %s" % path
        exit(1)

    return ssh, sftp

def load_config_file(config):
    if type(config) != dict:
        print "ERROR: Improperly formatted configuration file (not a YAML object)"
        exit(1)

    for v in ("pc2_dir", "scoreboard_files", "web_server", "web_username", "web_path"):
        if not config.has_key(v):
            print "ERROR: Config file missing '%s' value" % v
            exit(1)

    if not config.has_key("freeze_message"):
        config["freeze_message"] = "The scoreboard is frozen."

    pc2_dir = config["pc2_dir"]
    if not os.path.exists(config["pc2_dir"]):
        print "ERROR: Specified pc2_dir (%s) does not exist" % pc2_dir
        exit(1)

    scoreboard_files = config["scoreboard_files"]

    if type(scoreboard_files) != list:
        print "ERROR: value of scoreboard_files should be a list of values"
        exit(1)
        
    for f in scoreboard_files:
        ff = pc2_dir + "/" + f
        if not os.path.exists(ff):
            print "ERROR: Scoreboard file '%s' does not exist" + ff
            exit(1)

    ssh_web, sftp_web = connect_to_server(config["web_server"], config["web_username"], config["web_path"])

    has_ewteam = True
    for v in ("ewteam_server", "ewteam_username", "ewteam_path"):
        if not config.has_key(v):
            has_ewteam = False
            break

    if has_ewteam:
        if config["ewteam_server"] == config["web_server"]:
            ssh_ewteam = ssh_web
            sftp_ewteam = ssh_ewteam.open_sftp()            
            try:
                sftp_ewteam.chdir(config["ewteam_path"])
            except IOError, ioe:
                print "ERROR: Could not set SFTP client to directory %s" % config["ewteam_path"]
                exit(1)
        else:
            ssh_ewteam, sftp_ewteam = connect_to_server(config["ewteam_server"], config["ewteam_username"], config["ewteam_path"])
    else:
        ssh_ewteam = None
        sftp_ewteam = None
        
    return ssh_web, sftp_web, ssh_ewteam, sftp_ewteam


def generate_frozen_file(d, f, freeze_message):
    # TODO: Include timezone in message
    frozen_text = "<p style='font: bold 18px Arial, Sans-serif; color: red'>%s</p>\r\n" % freeze_message
    frozen_text += "<p style='font: 12px Arial, Sans-serif'>Scoreboard was frozen at %s</p>" % now_str()

    frozen_scoreboard_file = f.replace(".html", "-frozen.html")

    sbf = open(d + "/" + f)
    sb_src = sbf.read()
    sbf.close()

    sb_src = re.sub("BODY>\s*<TABLE", "BODY>\r\n%s\r\n<TABLE" % frozen_text, sb_src)

    sbf = open(d + "/" + frozen_scoreboard_file, "w")
    sbf.write(sb_src)
    sbf.close()

    return frozen_scoreboard_file


def upload_scoreboard(sftp_client, files, freeze, freeze_message, suffix, chmod = False):

    for d, f in files:

        if freeze:
            frozen_file = generate_frozen_file(d, f, freeze_message)
            localpath = "%s/%s" % (d,frozen_file)
        else:
            localpath = "%s/%s" % (d,f)

        try:
            if suffix is not None:
                fname = f.replace(".html", "-%s.html" % suffix)
            else:
                fname = f

            sftp_client.put(localpath, fname)
        except Exception, e:
            raise
            print "ERROR: Unable to upload file %s" % fname
            

        if chmod:
            try:
                sftp_client.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            except Exception, e:
                print "ERROR: Unable to chmod file %s" % fname
    
    log("Uploaded scoreboard")  


def upload_scoreboard_every(sftp_client, files, suffix, freeze_at, interval):

    last_modified = dict([ ( (d,f), 0.0 ) for (d,f) in scoreboard_files ])
    chmod = True

    while True:
        # Have there been any changes to the scoreboard?
        changed = False
        for ( (d,f), mtime) in last_modified.items():
            new_mtime = os.stat(d+"/"+f).st_mtime
            if new_mtime > mtime:
                changed = True
            last_modified[(d,f)] = new_mtime

        if changed:
            upload_scoreboard(sftp_client = sftp_client,
                              files = files,                     
                              freeze = False,
                              freeze_message = None,
                              suffix = suffix,
                              chmod = chmod)

            # We only want to chmod the first time we upload
            if chmod:
                chmod = False
        else:
            log("Scoreboard hasn't changed. Not uploading")

        if freeze_at is not None:
            td = freeze_at - datetime.now()
            tds = td.total_seconds()

            if tds < 0:
                break

            if tds < (FREEZE_WARNING_MINUTES * 60):
                log("ATTENTION: The scoreboard will be frozen in %s" % td_str(td))

        time.sleep(interval)


def freeze_ewteam(sftp, scoreboard_url, freeze_message):

    scoreboard_file = "./Team/iScoreBoard.php"  
    scoreboard_file_backup = "./Team/iScoreBoard.txt"

    try:
        sftp.stat(scoreboard_file)
    except IOError, ioe:
        log("EWTeam server doesn't seem to contain EWTeam (%s not found)" % (scoreboard_file))
        return False

    try:
        sftp.stat(scoreboard_file_backup)
        log("The EWTeam scoreboard is already frozen. You cannot re-freeze it.")
        return False
    except IOError, ioe:
        pass


    try:
        backupf = sftp.open(scoreboard_file_backup, "w")
        sftp.getfo(scoreboard_file, backupf)
        backupf.close()
    except Exception, e:
        log("Could not create backup of scoreboard file")
        return False

    if scoreboard_url[-1] != "/":
        scoreboard_url += "/"

    scoreboard_url = scoreboard_url + "Team/iScoreBoard.php"

    try:
        sb = urllib2.urlopen(scoreboard_url)
    except urllib2.HTTPError, he:
        log("EWTeam scoreboard not found.")
        log("%s produced error %s %s" % (scoreboard_url, he.code, he.msg))
        return False
    except Exception, e:
        log("Unexpected exception accessing scoreboard.")
        return False

    frozen_text = "<p style='font: bold 18px Arial, Sans-serif; color: red'>%s</p>\r\n" % freeze_message
    frozen_text += "<p style='font: 12px Arial, Sans-serif'>Scoreboard was frozen at %s (Central time)</p>" % now_str()

    sb_src = sb.read()
    sb_src = re.sub("body>\s*<table", "body>\r\n%s\r\n<table" % frozen_text, sb_src)


    try:
        sbf = sftp.open(scoreboard_file, "w")
        sbf.write(sb_src)
        sbf.close()
    except Exception, e:
        log("Could not write frozen scoreboard")
        return False

    log("Froze EWTeam scoreboard")  


def thaw_ewteam(sftp):
    scoreboard_file = "./Team/iScoreBoard.php"  
    scoreboard_file_backup = "./Team/iScoreBoard.txt"

    try:
        sftp.stat(scoreboard_file)
    except IOError, ioe:
        log("EWTeam server doesn't seem to contain EWTeam (%s not found)" % (scoreboard_file))
        return False

    try:
        sftp.stat(scoreboard_file_backup)
    except IOError, ioe:
        log("EWTeam server doesn't seem to contain a backup of the scoreboard PHP file (%s not found)" % (scoreboard_file))
        return False

    try:
        sbf = sftp.open(scoreboard_file, "w")
        sftp.getfo(scoreboard_file_backup, sbf)
        sbf.close()
    except Exception, e:
        log("Could not restore backup of scoreboard file")
        return False

    try:
        sftp.remove(scoreboard_file_backup)
    except Exception, e:
        log("Could not delete backup of scoreboard PHP")
        return False


    log("Thawed EWTeam scoreboard")  

### MAIN PROGRAM ###

if __name__ == "__main__":
    # Setup argument parser
    parser = ArgumentParser(description="scoreboard-publish")
    parser.add_argument('config', metavar='CONFIG_FILE', type=FileType('r'))
    parser.add_argument('--freeze', action="store_true")
    parser.add_argument('--thaw-ewteam', action="store_true")
    parser.add_argument('--suffix', metavar='SUFFIX', type=str, default=None)
    parser.add_argument('--update', metavar='SECONDS', type=int, default=0)
    parser.add_argument('--freeze-at', metavar='DATE_TIME', type=str, default=None)
    parser.add_argument('--freeze-suffix', metavar='SUFFIX', type=str, default=None)
    parser.add_argument('--verbose', action="store_true")

    args = parser.parse_args()

    if args.verbose:
        verbose = True

    try:
        config = yaml.load(args.config.read())
    except Exception, e:
        print "ERROR: Could not read configuration file"
        if verbose: raise 
        exit(1)

    ssh_web, sftp_web, ssh_ewteam, sftp_ewteam = load_config_file(config)

    if args.thaw_ewteam and sftp_ewteam is None:
        print "ERROR: --thaw-ewteam specified but no EWTeam server specified in configuration file"
        exit(1)

    scoreboard_files = [(config["pc2_dir"], f) for f in config["scoreboard_files"]]

    if args.update == 0:

        if args.freeze_at:
            print "ERROR: Cannot use --freeze-at without --update"
            exit(1)

        upload_scoreboard(sftp_client = sftp_web,
                          files = scoreboard_files,                     
                          freeze = args.freeze,
                          freeze_message = config["freeze_message"],
                          suffix = args.suffix,
                          chmod = True)
        
        if args.freeze and sftp_ewteam is not None:
            freeze_ewteam(sftp_ewteam, config["ewteam_scoreboard_url"], config["freeze_message"])

        if args.thaw_ewteam:
            thaw_ewteam(sftp_ewteam)

    elif args.update >= MIN_UPDATE_INTERVAL:
        if args.freeze:
            print "ERROR: Cannot use --freeze with --update"
            exit(1)

        if args.suffix is not None and args.freeze_at is not None:
            print "ERROR: Cannot use --freeze-at with --suffix"
            exit(1)             

        if args.thaw_ewteam:
            print "ERROR: Cannot use --thaw-ewteam with --update"
            exit(1)

        if args.freeze_at is not None:
            try:
                freeze_at = datetime.strptime(args.freeze_at, "%Y-%m-%d %H:%M")
            except ValueError, ve:
                print "ERROR: Invalid date %s (should be YYYY-MM-DD HH:MM)"
                exit(1)

            if freeze_at < datetime.now():
                print "ERROR: You have specified a freezing time that has already passed"
                exit(1)

            log("The scoreboard will be frozen at %s (in %s)" % (args.freeze_at, td_str(freeze_at - datetime.now())))
        else:
            freeze_at = None

        upload_scoreboard_every(sftp_client = sftp_web,
                                files = scoreboard_files,
                                suffix = args.suffix,
                                freeze_at = freeze_at,
                                interval = args.update)

        
        if freeze_at is not None:
            # Freeze the scoreboard
            log("Uploading frozen scoreboard")
            upload_scoreboard(sftp_client = sftp_web,
                  files = scoreboard_files,                     
                  freeze = True,
                  freeze_message = config["freeze_message"],
                  suffix = None,
                  chmod = False)

            if sftp_ewteam is not None:
                freeze_ewteam(sftp_ewteam, config["ewteam_scoreboard_url"], config["freeze_message"])

        if args.freeze_suffix is not None:
            log("Beginning upload to post-freeze suffix (%s)" % args.freeze_suffix)
            upload_scoreboard_every(sftp_client = sftp_web,
                                    files = scoreboard_files,
                                    suffix = args.freeze_suffix,
                                    freeze_at = None,
                                    interval = args.update)

    else:
        print "ERROR: Update interval must be at least %i seconds" % MIN_UPDATE_INTERVAL
        exit(1)

