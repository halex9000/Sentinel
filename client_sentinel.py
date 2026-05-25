###############################################################################################################
# Program: client_sentinel.py
#  Author: Alessandro Carichini
#    Date: 11-05-2026
#        : 21-05-2026
#    Note: Client for Monitoring Server with api call
#
# pip install requests
# pip install psutil
###############################################################################################################
# switch
#
# --registry = registra il server sul db
# default = effettua l'aggiornamento sul db verificando che hostname sia censito nella tabella SERVERS
#
###############################################################################################################

import os
import platform
import time
from datetime import datetime
import argparse
import psutil
import socket
import requests

###############################################################################################################
HOME = True
SSL_REAL = False
MAX_RETRY_API = 3
DEBUG = True

BASE_URL = "https://localhost"

if not SSL_REAL:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = BASE_URL+"/services/api_sentinel.php"

###############################################################################################################

parser = argparse.ArgumentParser()

parser.add_argument(
    "action",
    nargs="?",
    default="standard",
    choices=["standard", "registry"]
)

args = parser.parse_args()

if args.action == "standard":
    ACTION = 2
elif args.action == "registry":
    ACTION = 1
    print("Registrazione Server:")
    server_desc = input("Descrizione: ")
    server_url = input("URL: ")
    server_note = input("Note: ")
    server_coll = input("DataCenter: ")
    sentinel = 1


def get_active_ips_windows():
    active_ips = set()  # Utilizzo di un set per evitare duplicati
    connections = psutil.net_connections(kind='inet')
    for conn in connections:
        if conn.family == socket.AF_INET and not conn.laddr.ip.startswith("127.") and not conn.laddr.ip.startswith("0.0."):
            active_ips.add(conn.laddr.ip)
    
    return ';'.join(active_ips)

def get_disk_usage():
    disk_info = {}
    diskp = psutil.disk_partitions()

    for partition in diskp:

        if partition.mountpoint:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info[partition.device] = {
                    "mountpoint": partition.mountpoint,
                    "total": round(usage.total / (1024 ** 3), 2),  # Converti in GB
                    "used": round(usage.used / (1024 ** 3), 2),
                    "free": round(usage.free / (1024 ** 3), 2),
                    "percent": usage.percent
                }
            except:
                disk_info[partition.device] = {
                    "mountpoint": "",
                    "total": 0,
                    "used": 0,
                    "free": 0,
                    "percent": 0
                }


    return disk_info

def API_CALL(API_URL,payload,SSL_REAL):
    result = ""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    session = requests.Session()
    session.trust_env = False

    for tentativo in range(MAX_RETRY_API):
        try:
            response = session.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=(5, 30),
                verify=SSL_REAL
            )

            if DEBUG:
                print("HTTP:", response.status_code)
                print("BODY:", response.text)

            result = response.json()

            if response.status_code == 200:

                if result.get("status") == "duplicate":
                    print("** UNIQUE ")

                break 

            else:
                return {
                    "status": "error API",
                    "message": str(result)
                }                

        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "message": f"Timeout tentativo {tentativo+1}/{MAX_RETRY_API}"
            }                

        except requests.exceptions.ConnectionError as e:
            return {
                "status": "error",
                "message": f"Connessione fallita {tentativo+1}/{MAX_RETRY_API}: {e}"
            }                

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Errore requests {tentativo+1}/{MAX_RETRY_API}: {e}"
            }                

        except Exception as e:
            return {
                "status": "error",
                "message": f"Errore generico {tentativo+1}/{MAX_RETRY_API}: {e}"
            }                

        if (tentativo < MAX_RETRY_API - 1):
            time.sleep(2)

    else:      
        result = {
                "status": "error",
                "message": "Tutti tentativi falliti"
        }

    return result

########################################################################################### MAIN
if __name__ == "__main__":
    PLATFORM = platform.system()
    HOSTNAME = platform.node()
    addrList = socket.getaddrinfo(socket.gethostname(), None)
    IPADDRESS = addrList[len(addrList)-1][4][0]
    USERNAME = os.getenv('USERNAME').upper()
    data_ora_attuale = datetime.now()   
    datamon = data_ora_attuale.strftime("%Y/%m/%d %H:%M")    
    boot_time_timestamp = psutil.boot_time()
    boot_time_datetime = datetime.fromtimestamp(boot_time_timestamp)
    UPTIME = boot_time_datetime.strftime("%Y-%m-%d %H:%M:%S")

    NETWORK_IP = get_active_ips_windows()
    disk_info = get_disk_usage()

    if DEBUG:
        print(f"Server: {HOSTNAME} ")
        print(f"Platform: {PLATFORM} ")
        print(f"Network: {NETWORK_IP} ")
        print(f"Uptime: {UPTIME}")

    if ACTION == 1:
        ## Registra Server
        payload = {
            "action": "server",
            "SERVER_IP": NETWORK_IP,
            "SERVER_NAME": HOSTNAME,
            "SERVER_DESCR": server_desc,
            "URL": server_url,
            "NOTE": server_note,
            "COLLOCAZIONE": server_coll,
            "MAX_DELAY": 0,
            "SENTINEL": sentinel,
            "ATTIVO": 1
        }
        response = API_CALL(API_URL,payload,SSL_REAL)
        result = response.json()

    else:
        # Aggiorna la tabella solo se il server è stato registrato
        payload_check = {
            "action": "verify",
            "SERVER_NAME": HOSTNAME
        }

        response = API_CALL(API_URL,payload_check,SSL_REAL)

        if response["status"] == "not_found":
            print(f"Server {HOSTNAME} not registred")
        else:
            ## Update Sentinel Server
            for device, info in disk_info.items():
                if info['mountpoint'] != "":
                    print(f"Device: {device} - {info['total']} GB - Used {info['percent']}% ")

                    payload = {
                        "action": "sentinel",
                        "DATAMON": datamon,
                        "HOSTNAME": HOSTNAME,
                        "PLATFORM": PLATFORM,
                        "UPTIME": UPTIME,
                        "NETWORK_IP": NETWORK_IP,
                        "DISK_MOUNT": info['mountpoint'],
                        "DISK_SIZE": info['total'],
                        "DISK_USED": info['used'],
                        "DISK_FREE": info['free'],
                        "DISK_PERC": info['percent'],
                        "USERNAME": USERNAME
                    }

                    if DEBUG:
                        print(payload)
            
                    result = API_CALL(API_URL,payload,SSL_REAL)

                    print(result)

