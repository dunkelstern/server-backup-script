#!/usr/bin/env python
# -*- coding: utf-8 -*-

import daemon # from python-daemon
import schedule # from schedule
import ConfigParser, os, sys, glob, argparse, time, lockfile, grp, pwd, datetime, socket

remote = None
remoteUser = None

def log(message):
    sys.stdout.write("{date:%Y-%m-%d %H:%M:%S} {hostname} backup[{pid}]: {message}\n".format(
        date = datetime.datetime.today(),
        hostname = socket.gethostname(),
        pid = os.getpid(),
        message = message))
    sys.stdout.flush()
    return

def log_error(message):
    sys.stderr.write("{date:%Y-%m-%d %H:%M:%S} {hostname} backup[{pid}]: {message}\n".format(
        date = datetime.datetime.today(),
        hostname = socket.gethostname(),
        pid = os.getpid(),
        message = message))
    sys.stderr.flush()
    return

def execute_rsync(taskConfig):
    global remote, remoteUser
    # rsync -qrlHpAXogDtSxz --rsh='ssh -l {remoteUser}' --delete --exclude=PATTERN '{src}' {host}:'{dest}'

    global remote, remoteUser

    log("Executing rsync for '{}'".format(taskConfig.get('backup', 'description')))

    # execute pre copy command
    if taskConfig.has_option('copy', 'pre_sync_command'):
        result = os.system(taskConfig.get('copy', 'pre_sync_command'))
        if not result == 0:
            log_error("Error executing pre sync command for '{}'".format(taskConfig.get('backup', 'description')))
            return
    
    # build exclusion list
    e = []
    if taskConfig.has_option('exclude', 'files'):
        for file in taskConfig.get('exclude', 'files').split(","):
            e.append(file.strip())

    if taskConfig.has_option('exclude', 'dirs'):
        for dir in taskConfig.get('exclude', 'dirs').split(","):
            if not dir[-1] == '/':
                e.append(dir.strip() + "/")
            else:
                e.append(dir.strip())

    if taskConfig.has_option('exclude', 'patterns'):
        for pat in taskConfig.get('exclude', 'patterns').split(","):
            e.append(pat.strip())

    exclusions = ""
    for ex in e:
        exclusions = exclusions + " --exclude='{}'".format(ex)

    # run rsync
    command = "rsync -qrlHpAXogDtSxz --rsh='ssh -l {remoteUser}' --delete {exclusions} '{src}' {host}:'{dest}'".format(
        remoteUser=remoteUser,
        exclusions=exclusions,
        src=taskConfig.get('rsync', 'source_dir'),
        host=remote,
        dest=taskConfig.get('rsync', 'destination_dir')
        )

    log(command)
    
    result = os.system(command)
    if not result == 0:
        log_error("Error executing rsync command for '{}'".format(taskConfig.get('backup', 'description')))

    # execute post sync command
    if taskConfig.has_option('copy', 'post_sync_command'):
        result = os.system(taskConfig.get('copy', 'post_sync_command'))
        if not result == 0:
            log_error("Error executing post sync command for '{}'".format(taskConfig.get('backup', 'description')))
            return
    return

    return

def execute_copy(taskConfig):
    global remote, remoteUser

    log("Executing copy for '{}'".format(taskConfig.get('backup', 'description')))

    # execute pre copy command
    if taskConfig.has_option('copy', 'pre_copy_command'):
        result = os.system(taskConfig.get('copy', 'pre_copy_command'))
        if not result == 0:
            log_error("Error executing pre copy command for '{}'".format(taskConfig.get('backup', 'description')))
            return
    
    # run copy
    command = "scp '{src}' {user}@{host}:'{dest}'".format(
        taskConfig.get('copy', 'source_file'),
        remoteUser,
        remote,
        taskConfig.get('copy', 'destination_file')
        )

    result = os.system(command)
    if not result == 0:
        log_error("Error executing copy command for '{}'".format(taskConfig.get('backup', 'description')))

    # execute post copy command
    if taskConfig.has_option('copy', 'post_copy_command'):
        result = os.system(taskConfig.get('copy', 'post_copy_command'))
        if not result == 0:
            log_error("Error executing post copy command for '{}'".format(taskConfig.get('backup', 'description')))
            return
    return

def execute_script(taskConfig):
    log("Executing script for '{}'".format(taskConfig.get('backup', 'description')))
    
    result = os.system(taskConfig.get('script', 'execute'))
    if taskConfig.get('script', 'expect') == 'exit_code':
        if not result == int(taskConfig.get('script', 'exit_code')):
            log_error("Error executing script command for '{}', exit code is {}".format(taskConfig.get('backup', 'description'), result))
    elif taskConfig.get('script', 'expect') == 'file':
        if not os.path.isfile(taskConfig.get('script', 'file')):
            log_error("Error executing script command for '{}', expected file missing".format(taskConfig.get('backup', 'description')))           
    return

def execute(taskConfig):
    method = taskConfig.get('backup', 'method', 'unknown')
    if method == 'rsync':
        execute_rsync(taskConfig)
    elif method == 'copy':
        execute_copy(taskConfig)
    elif method == 'script':
        execute_script(taskConfig)
    else:
        sys.stderr.write("Error: Unknown method '{}' in '{}'".format(method, taskConfig.get('backup', 'description')))
        return
    return

def schedule_task(taskConfig):
    parts = taskConfig.get('backup', 'schedule').split(' ')
    if len(parts) != 4:
        sys.stderr.write("Error: Invalid schedule format: '{}' (should be: '<minute> <hour> <day> <month>') for '{}'".format(taskConfig.get('backup', 'schedule')), taskConfig.get('backup', 'description'))
        return
    if parts[3] == '*':
        # schedule every month
        if parts[2] == '*':
            # schedule every day
            if parts[1] == '*':
                # schedule every hour
                if parts[0] == '*':
                    # schedule every minute
                    log("Scheduling task '{}' every minute".format(taskConfig.get('backup', 'description')))
                    schedule.every(1).minutes.do(execute, taskConfig)
                else:
                    # at this time every hour
                    log("Scheduling task '{}' every hour at {:02d}".format(taskConfig.get('backup', 'description'), int(parts[0])))
                    schedule.every().hour.at(":{:02d}".format(int(parts[0]))).do(execute, taskConfig)
            else:
                # at this time every day
                log("Scheduling task '{}' every day at {:02d}:{:02d}".format(taskConfig.get('backup', 'description'), int(parts[1]), int(parts[0])))
                schedule.every().day.at("{:02d}:{:02d}".format(int(parts[1]), int(parts[0]))).do(execute, taskConfig)
        else:
            # at this day and time every month
            log("Scheduling task '{}' every month at the {:02d}. at {:02d}:{:02d}".format(taskConfig.get('backup', 'description'), int(parts[2]), int(parts[1]), int(parts[0])))
            return
    else:
        # once a year in this month
        log("Scheduling task '{}' every year at the {:02d}-{:02d} at {:02d}:{:02d}".format(taskConfig.get('backup', 'description'), int(parts[3]), int(parts[2]), int(parts[1]), int(parts[0])))
        return
    return

def run(cfg, configToExecute):
    global remote, remoteUser
    remote     = cfg.get('remote', 'host')
    remoteUser = cfg.get('remote', 'user')
    
    # get task configs
    configs    = glob.glob(cfg.get('backup', 'task_dir', '/etc/backup/tasks/') + "*.conf")
    tasks      = []

    if (configToExecute == None):
        # load all config files
        for config in configs:
            cfg = ConfigParser.ConfigParser()
            cfg.read(config)
            tasks.append(cfg)

        # setup timers for each task
        for task in tasks:
            schedule_task(task)

        # run the scheduler loop
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        # just execute the config then exit
        config = cfg.get('backup', 'task_dir', '/etc/backup/tasks/') + configToExecute
        cfg = ConfigParser.ConfigParser()
        cfg.read(config)
        execute(cfg)
    return

def main():
    # parse command line
    parser = argparse.ArgumentParser(description='Backup daemon')
    parser.add_argument('-c', '--config',
                       default='/etc/backup/backup.conf',
                       help='configuration file to read (defaults to /etc/backup/backup.conf)')
    parser.add_argument('-e', '--execute',
                       default=None,
                       help='execute task instantly and then exit')
    parser.add_argument('-f', '--foreground',
                       action='store_const', const=1,
                       help='do not daemonize, run in foreground')

    args = parser.parse_args()

    # open main config file
    if not os.path.isfile(args.config):
        log_error("Error: Could not open config file")
        sys.exit(1)

    cfg = ConfigParser.ConfigParser()
    cfg.read(args.config)

    if (args.foreground == 1) or (not args.execute == None):
        run(cfg, args.execute)
    else:
        context = daemon.DaemonContext(
            working_directory=cfg.get('backup', 'work_dir', '/tmp'),
            umask=0o002,
            pidfile=lockfile.FileLock(cfg.get('backup', 'pid_file', '/var/run/backup.pid')),
        )

        uid = pwd.getpwnam(cfg.get('backup', 'uid', 'backup')).pw_uid
        gid = grp.getgrnam(cfg.get('backup', 'gid', 'backup')).gr_gid
        context.uid = uid
        context.gid = gid

        # TODO: Signal map SIGUSR1 to "reload all config"       
        with context:
            run(cfg, None)

if __name__ == '__main__':
    main()
