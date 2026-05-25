###############################################################################################################
# Program: server_sentinel.py
#  Author: Alessandro Carichini
#    Date: 15-12-2023
#        : 21-05-2026
#    Note: Monitoring Server Status
###############################################################################################################
#  - Verifica spazio disco (disk_space) every 2 hour
#  - Heartbeat (hello_world) every day 
#  - I client vanno schedulati ogni 2 ore
#  - Report verifica se mancano record nell'arco della giornata
###############################################################################################################

import MySQLdb as mdb
from dbcommon import *

import argparse

from datetime import datetime
import platform
import smtplib
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

LIMIT_MAX = "94"

MYSQLDB = "sentinel"
TAB_SENTINEL = "RESOURCES"
TAB_SERVERS = "SERVERS"

EMAIL_FROM="from@server.net"
EMAIL_TO="toclient@server.net"
EMAIL_CC=""
SMTP_RELAY = "pop.gmail.com"

query_sentinel_disks = f"""
    SELECT S.*
    FROM {TAB_SENTINEL} S
    INNER JOIN (
        SELECT HOSTNAME, DISK_MOUNT, MAX(DATAMON) AS MaxDATAMON FROM {TAB_SENTINEL}
        WHERE DATE(DATAMON) = CURDATE() 
        GROUP BY HOSTNAME, DISK_MOUNT
    ) MaxDates ON S.HOSTNAME = MaxDates.HOSTNAME
        AND S.DISK_MOUNT = MaxDates.DISK_MOUNT
        AND S.DATAMON = MaxDates.MaxDATAMON;
"""

query_sentinel_hello = f"""
    SELECT
        SRV.SERVER_NAME,SEN.DATAMON,SRV.SERVER_DESCR,SRV.COLLOCAZIONE
    FROM {TAB_SERVERS} SRV
    LEFT JOIN (
        SELECT
            HOSTNAME,
            MAX(DATAMON) AS DATAMON
        FROM {TAB_SENTINEL}
        WHERE DATE(DATAMON) = CURDATE()
        GROUP BY HOSTNAME
    ) SEN
    ON SRV.SERVER_NAME = SEN.HOSTNAME
    WHERE SRV.ATTIVO = 1 AND SRV.SENTINEL = 1
    ORDER BY SRV.SERVER_PROG
"""

query_ping = " SELECT * FROM "+TAB_SERVERS+" WHERE ATTIVO = 1"

msg = ""

def SendMailHTML(mailfrom, mailto, mailcc, mailobj, mailmsg, smtp, allegato):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = mailobj
    msg['From'] = mailfrom
    msg['to'] = mailto
    msg['cc'] = mailcc

#	part1 = MIMEText(text, 'plain')
    part = MIMEText(mailmsg, 'html', 'utf-8')
    msg.attach(part)

    if allegato is not None:
        if os.path.isfile(allegato):
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(allegato, "rb").read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(allegato))
            msg.attach(part)

    aMailX = mailcc.split(",") + mailto.split(",")
    # Send the message via local SMTP server.
    s = smtplib.SMTP(smtp)
    s.sendmail(mailfrom, aMailX, msg.as_string())
    s.quit()


def ConnectMySQL(MYSQLDB):
    try:
        conMy = mdb.connect(MYSQLHOST, MYSQLUSER, MYSQLPWD, MYSQLDB,charset='utf8');

    except mdb.Error as e:
        print("MySQL Error [%d]: %s" % (e.args[0], e.args[1]))
        sys.exit(1)    

    return conMy

def GetField(record,nCampo):
    if record is None:
        return ""
    else:
        return str(record[nCampo])

def Check_Disks(curMy,query):
    curMy.execute(query)    
    msg = ""
    header = "<table border=1><th>Data</th><th>Hostname</th><th>Volume</th><th>GB</th><th>Free GB</th><th>Utilizzo</th>"
    for campo in curMy.fetchall():
        data = GetField(campo,1)
        hostname = GetField(campo,2)
        system = GetField(campo,3)
        uptime = GetField(campo,4)
        network = GetField(campo,5)
        disk_mount = GetField(campo,6)
        disk_size = GetField(campo,7)
        disk_used = GetField(campo,8)
        disk_free = GetField(campo,9)
        disk_perc = GetField(campo,10)

        if float(disk_perc) > int(LIMIT_MAX):
            msg = msg + f"<tr><td width=10%>{data}</td><td width=10%>{hostname}</td><td width=10%>{disk_mount}</td><td width=10%>{disk_size}</td><td width=10%>{disk_free}</td><td width=10%>{disk_perc}</td></tr><br>"

    if msg != "":
        msg = "<b>Disk space warning:</b><br><br>\n"+header+msg+"</table>"

    return msg

def Check_Hellos(curMy,query):
    # Verifica Hello World
    curMy.execute(query)
    msg = ""
    header = "<li>"
    for campo in curMy.fetchall():
        hostname = GetField(campo,0)
        data = GetField(campo,1)
        descr = GetField(campo,2)
        dc = GetField(campo,3)
        #print(f"{hostname} - {data}")
        if (data == "None"):
            msg = msg + f"<ul>{hostname} {descr} - {dc}</ul><br>\n"

    if msg != "":
        msg = "<b>Server with no heartbeat: </b>\<br><br>\n"+header+msg+"</ul>"
        print(msg)

    return msg

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "action",
        nargs="?",                  # argomento opzionale
        default="",         # se non passato
        choices=["disks", "hello"]
    )

    args = parser.parse_args()

    # Connessione DB
    conMy = ConnectMySQL(MYSQLDB)
    curMy = conMy.cursor()

    msg=""
    # Verifica Spazio su disco
    if args.action == "disks":
        msg = Check_Disks(curMy,query_sentinel_disks)
        EMAIL_OBJ="Sentinel Server - CHECK SPACE"

    # Verifica Hello World
    if args.action == "hello":
        msg = Check_Hellos(curMy,query_sentinel_hello)
        EMAIL_OBJ="Sentinel Server - CHECK SERVERS"

    # Se ci sono errori manda una email 
    if msg != "":
        print(f"SEND EMAIL {EMAIL_TO}")
        print(msg)
        SendMailHTML(EMAIL_FROM, EMAIL_TO, EMAIL_CC, EMAIL_OBJ, msg, SMTP_RELAY,None)
    else:
        print("no messages")
    

    curMy.close()
    conMy.close()
