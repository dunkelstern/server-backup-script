#!/bin/bash
USER="backup"
REMOTE="example.com"
FROM='"Server" <backup@example.com>'

EMAILS="user@example.com"

# local package list
dpkg --get-selections|grep install|cut -f 1|sed -e 's/:amd64//'|sort >/tmp/packagelist.local

# remote package list
ssh ${USER}@${REMOTE} 'dpkg --get-selections' |grep install|cut -f 1|sed -e 's/:amd64//'|sort >/tmp/packagelist.remote

# diff
diff -au0 /tmp/packagelist.remote /tmp/packagelist.local |egrep -v '@@|---|\+\+\+' >/tmp/packagechanges.log

if [ $(wc -l /tmp/packagechanges.log) -ne 0 ] ; then
	for mail in ${EMAILS} ; do

		/usr/sbin/sendmail $mail <<EOF
From: ${FROM}
To: "Admin" <$mail>
Subject: Installed packages differ

Installed packages on live and backup system differ, please fix:

$(cat /tmp/packagechanges.log)
EOF

	done
fi