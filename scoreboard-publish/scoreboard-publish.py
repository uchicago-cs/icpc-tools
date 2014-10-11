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

try:
    import requests
    import yaml
    import paramiko
except ImportError, ie:
    print "Your system is missing a required software library to run this script."
    print "Try running the following:"
    print 
    print "    pip install --user requests PyYAML paramiko"
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

    try:
        ssh_web = paramiko.SSHClient()
        ssh_web.load_system_host_keys()
        ssh_web.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        ssh_web.connect(config["web_server"], username=config["web_username"])
        sftp_web = ssh_web.open_sftp()
    except paramiko.AuthenticationException, ae:
        print "ERROR: Authentication error connection to %s" % config["web_server"]
        exit(1)
    except paramiko.SSHException, sshe:
        print "ERROR: SSH error when connecting to %s" % config["web_server"]
        exit(1)        
    except socket.error:
        print "ERROR: Network error when connecting to %s" % config["web_server"]
        exit(1)        

    try:
        stdin, stdout, stderr = ssh_web.exec_command('stat %s' % config["web_path"])
        so = stdout.read()
        se = stderr.read()

        if len(se) > 0:
            print "ERROR: Error when trying to read remote web directory" % config["web_server"]
            print
            print "stderr: %s" % (se)
            exit(1)
    except SSHException, sshe:
        print "ERROR: SSH error when connecting to %s (couldn't stat remote directory)" % config["web_server"]
        exit(1)        

    try:
        sftp_web.chdir(config["web_path"])
    except IOError, ioe:
        print "ERROR: Could not set SFTP client to directory %s" % config["web_path"]
        exit(1)        
        
    return ssh_web, sftp_web, None, None


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

   # pp(config)

    ssh_web, sftp_web, ssh_ewteam, sftp_ewteam = load_config_file(config)

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

        if args.thaw_ewteam:
            # Thaw the EWTeam scoreboard
            pass

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
                upload_scoreboard(sftp_client = sftp_web,
                                  files = scoreboard_files,                     
                                  freeze = False,
                                  freeze_message = None,
                                  suffix = args.suffix,
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

            time.sleep(args.update)
        
        if freeze_at is not None:
            # Freeze the scoreboard
            log("Uploading frozen scoreboard")
            upload_scoreboard(sftp_client = sftp_web,
                  files = scoreboard_files,                     
                  freeze = True,
                  freeze_message = config["freeze_message"],
                  suffix = None,
                  chmod = chmod)

    else:
        print "ERROR: Update interval must be at least %i seconds" % MIN_UPDATE_INTERVAL
        exit(1)

