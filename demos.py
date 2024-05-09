import os
import json
import requests
import datetime
from bs4 import BeautifulSoup
import zoneinfo
import tzlocal
from python_utils import converters
import logging
import rarfile
import subprocess
import shutil
from demoparser2 import DemoParser
import hashlib
import traceback
from awpy import Demo
from awpy.stats.adr import adr
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

HLTV_COOKIE_TIMEZONE = "Europe/Copenhagen"
HLTV_ZONEINFO = zoneinfo.ZoneInfo(HLTV_COOKIE_TIMEZONE)
LOCAL_TIMEZONE_NAME = tzlocal.get_localzone_name()
LOCAL_ZONEINFO = zoneinfo.ZoneInfo(LOCAL_TIMEZONE_NAME)
FLARE_SOLVERR_URL = "http://localhost:8191/v1"
TEAM_MAP_FOR_RESULTS = []

def compute_file_hash(filename):
    """Compute the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
    
def get_parsed_page(url):
    headers = {
        "referer": "https://www.hltv.org/stats",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    cookies = {"hltvTimeZone": HLTV_COOKIE_TIMEZONE}
    post_body = {"cmd": "request.get", "url": url, "maxTimeout": 60000}

    try:
        response = requests.post(FLARE_SOLVERR_URL, headers=headers, json=post_body)
        response.raise_for_status()
        json_response = response.json()
        if json_response.get("status") == "ok":
            html = json_response["solution"]["response"]
            return BeautifulSoup(html, "lxml")
    except requests.RequestException as e:
        logging.error(f"Error making HTTP request: {e}")
    return None

def _get_all_teams():
    if not TEAM_MAP_FOR_RESULTS:
        teams = get_parsed_page("https://www.hltv.org/stats/teams?minMapCount=0")
        logging.debug("get_all_teams")
        for team in teams.find_all("td", {"class": ["teamCol-teams-overview"]}):
            team = {
                "id": converters.to_int(team.find("a")["href"].split("/")[-2]),
                "name": team.find("a").text,
                "url": "https://hltv.org" + team.find("a")["href"],
            }
            TEAM_MAP_FOR_RESULTS.append(team)

def _findTeamId(teamName: str):
    _get_all_teams()
    for team in TEAM_MAP_FOR_RESULTS:
        if team["name"] == teamName:
            return team["id"]
    return None

def _padIfNeeded(numberStr: str):
    if int(numberStr) < 10:
        return str(numberStr).zfill(2)
    else:
        return str(numberStr)

def _monthNameToNumber(monthName: str):
    if monthName == "Augu":
        monthName = "August"
    return datetime.datetime.strptime(monthName, "%B").month

def get_results():
    results = get_parsed_page("https://www.hltv.org/results")
    results_list = []
    pastresults = results.find_all("div", {"class": "results-holder"})

    for result in pastresults:
        resultDiv = result.find_all("div", {"class": "result-con"})

        for res in resultDiv:
            resultObj = {}
            resultObj["url"] = "https://hltv.org" + res.find("a", {"class": "a-reset"}).get("href")
            resultObj["match-id"] = converters.to_int(res.find("a", {"class": "a-reset"}).get("href").split("/")[-2])

            if res.parent.find("span", {"class": "standard-headline"}):
                dateText = (res.parent.find("span", {"class": "standard-headline"})
                            .text.replace("Results for ", "")
                            .replace("th", "")
                            .replace("rd", "")
                            .replace("st", "")
                            .replace("nd", ""))

                dateArr = dateText.split()
                dateTextFromArrPadded = (_padIfNeeded(dateArr[2]) + "-"
                                         + _padIfNeeded(_monthNameToNumber(dateArr[0])) + "-"
                                         + _padIfNeeded(dateArr[1]))
                dateFromHLTV = datetime.datetime.strptime(dateTextFromArrPadded, "%Y-%m-%d").replace(tzinfo=HLTV_ZONEINFO)
                dateFromHLTV = dateFromHLTV.astimezone(LOCAL_ZONEINFO)
                resultObj["date"] = dateFromHLTV.strftime("%Y-%m-%d")
            else:
                dt = datetime.date.today()
                resultObj["date"] = str(dt.day) + "/" + str(dt.month) + "/" + str(dt.year)

            if res.find("td", {"class": "placeholder-text-cell"}):
                resultObj["event"] = res.find("td", {"class": "placeholder-text-cell"}).text
            elif res.find("td", {"class": "event"}):
                resultObj["event"] = res.find("td", {"class": "event"}).text
            else:
                resultObj["event"] = None

            if res.find_all("td", {"class": "team-cell"}):
                resultObj["team1"] = res.find_all("td", {"class": "team-cell"})[0].text.lstrip().rstrip()
                resultObj["team1score"] = converters.to_int(res.find("td", {"class": "result-score"})
                                                            .find_all("span")[0]
                                                            .text.lstrip()
                                                            .rstrip())
                resultObj["team1-id"] = _findTeamId(resultObj["team1"])
                resultObj["team2"] = res.find_all("td", {"class": "team-cell"})[1].text.lstrip().rstrip()
                resultObj["team2-id"] = _findTeamId(resultObj["team2"])
                resultObj["team2score"] = converters.to_int(res.find("td", {"class": "result-score"})
                                                            .find_all("span")[1]
                                                            .text.lstrip()
                                                            .rstrip())
            else:
                resultObj["team1"] = None
                resultObj["team1-id"] = None
                resultObj["team1score"] = None
                resultObj["team2"] = None
                resultObj["team2-id"] = None
                resultObj["team2score"] = None

            results_list.append(resultObj)

    return results_list

def get_results_with_demo_links():
    results_list = get_results()
    root_directory = os.getcwd()

    for result in results_list:
        # Early fetch of the result page to determine tourney-mode
        url = result["url"]
        result_page = get_parsed_page(url)
        
        tourney_mode_data = None
        if result_page:
            tourney_mode_element = result_page.find('div', {'class': 'standard-box veto-box'})
            if tourney_mode_element:
                tourney_mode_data = tourney_mode_element.find("div", {"class": "padding preformatted-text"}).text
                result['tourney-mode'] = "online" if "(Online)" in tourney_mode_data else "lan" if "(LAN)" in tourney_mode_data else "unknown"
            else:
                result['tourney-mode'] = "unknown"
        
        # Now check for existing directory
        event_directory = os.path.join(root_directory, result['tourney-mode'], result['event'])
        all_directories = os.listdir(event_directory) if os.path.exists(event_directory) else []
        match_directory_exists = any(dir.startswith(str(result['match-id'])) for dir in all_directories)
        
        if match_directory_exists:
            logging.debug(f"A directory starting with match ID {result['match-id']} exists. Skipping...")
            continue

        logging.debug("Attempting to fetch demo link and tourney mode info")

        if result_page:
            demo_link_element = result_page.find('a', {'class': 'stream-box'})
            if demo_link_element:
                demo_link = demo_link_element.get('data-demo-link')
                if demo_link:
                    demo_link = "https://www.hltv.org" + demo_link
                    result["demo-link"] = demo_link
                    logging.info(demo_link)
                    download_demo_file(demo_link, result)
            else:
                result["demo-link"] = None
        else:
            result["demo-link"] = None

    return results_list

def download_demo_file(demo_link, result, api_url=FLARE_SOLVERR_URL):
    try:
        headers = {"Content-Type": "application/json"}
        filename = demo_link.split("/")[-1] + ".rar"
        url_cookie = "https://hltv.org/results"
        data = {"cmd": "request.get", "url": url_cookie, "maxTimeout": 60000}
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()

        response_data = json.loads(response.content)
        cookies = {cookie["name"]: cookie["value"] for cookie in response_data["solution"]["cookies"]}
        user_agent = response_data["solution"]["userAgent"]

        demo_file = requests.get(demo_link, cookies=cookies, headers={"User-Agent": user_agent})
        demo_file.raise_for_status()

        with open(filename, "wb") as f:
            f.write(demo_file.content)
        logging.info(f"Demo downloaded successfully to {filename}")

        if not os.path.exists("extracted_files"):
            os.makedirs("extracted_files")

        with rarfile.RarFile(filename) as rf:
            rf.extractall("extracted_files")
            extracted_files = rf.namelist()
        logging.info(f"File extracted successfully to extracted_files/")
        
        for file in extracted_files:
            if file.endswith('.dem') and not (file.endswith('-p1.dem') or file.endswith('-p2.dem') or file.endswith('-p3.dem')):
                try:
                    parser = DemoParser(f"extracted_files/{file}")
                    parsed_demo = Demo(file=f"extracted_files/{file}")
    
                    logging.debug("Parsing started")
                    logging.debug(f"File: {file}")
    
                    last_tick = parser.parse_event("round_end")["tick"].to_list()[-1]
                    crosshairs = parser.parse_ticks(["crosshair_code"], ticks=[last_tick])
                    max_tick = parser.parse_event("round_end")["tick"].max()
                    wanted_fields = ["kills_total", "deaths_total", "mvps", "headshot_kills_total", "ace_rounds_total", "4k_rounds_total", "3k_rounds_total"]
                    scoreboard = parser.parse_ticks(wanted_fields, ticks=[max_tick])
    
                    file_hash = compute_file_hash(f"extracted_files/{file}")
    
                    # Creating directories and saving parsed data to JSON files
                    output_directories = [f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/{dirname}"
                                          for dirname in ["kills", "damages", "bombs", "smokes", "infernos", "weapon_fires", "crosshair_codes", "scoreboard", "adr", "bombs"]]
                    for output_dir in output_directories:
                        os.makedirs(output_dir, exist_ok=True)
    
                    crosshairs.to_json(f'{output_directories[6]}/{file_hash}.json', indent=1)
                    scoreboard.to_json(f'{output_directories[7]}/{file_hash}.json', indent=1)
                    parsed_demo.kills.to_json(f'{output_directories[0]}/{file_hash}.json', indent=1)
                    parsed_demo.damages.to_json(f'{output_directories[1]}/{file_hash}.json', indent=1)
                    parsed_demo.smokes.to_json(f'{output_directories[3]}/{file_hash}.json', indent=1)
                    parsed_demo.infernos.to_json(f'{output_directories[4]}/{file_hash}.json', indent=1)
                    parsed_demo.weapon_fires.to_json(f'{output_directories[5]}/{file_hash}.json', indent=1)
                    parsed_demo.bomb.to_json(f'{output_directories[9]}/{file_hash}.json', indent=1)
                    adr(parsed_demo).to_json(f'{output_directories[8]}/{file_hash}.json', indent=1)
                    
                    logging.debug("Parsing finished")
                    logging.info("Parsed file saved")
                except Exception as e:
                    logging.error(f"Failed to parse {file} due to an error: {e}")
                    continue  # Skip this file and move to the next processing other files even if this one fails.
            else:
                logging.info(f"Ignoring file {file} because it's not a .dem file")


        os.remove(filename)
        logging.debug(f"Deleted {filename}")

    except requests.RequestException as e:
        logging.error(f"Error downloading demo file: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {type(e).__name__} - {str(e)}")
        logging.error(traceback.format_exc())
    finally:
        # Cleanup code
        if os.path.exists("extracted_files"):
            shutil.rmtree("extracted_files")
            logging.debug("Deleted extracted files")

if __name__ == "__main__":
    logging.info("Results with demo links:")
    logging.info(get_results_with_demo_links())
