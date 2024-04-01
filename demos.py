import os
import json
import requests
import datetime
from bs4 import BeautifulSoup
import zoneinfo
import tzlocal
from python_utils import converters
import pprint
import rarfile
import subprocess
import shutil
from demoparser2 import DemoParser
import hashlib
from awpy import Demo
from awpy.stats.adr import adr

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
        # Read file in chunks of 4K
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
        print(f"Error making HTTP request: {e}")
    return None

def _get_all_teams():
    if not TEAM_MAP_FOR_RESULTS:
        teams = get_parsed_page("https://www.hltv.org/stats/teams?minMapCount=0")
        print("get_all_teams")
        for team in teams.find_all(
            "td",
            {
                "class": ["teamCol-teams-overview"],
            },
        ):
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
    # Check for the input "Augu" and convert it to "August"
    # This is necessary because the input string may have been sanitized
    # by removing the "st" from the day numbers, such as "21st" -> "21"
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

            resultObj["url"] = "https://hltv.org" + res.find(
                "a", {"class": "a-reset"}
            ).get("href")

            resultObj["match-id"] = converters.to_int(
                res.find("a", {"class": "a-reset"}).get("href").split("/")[-2]
            )

            if res.parent.find("span", {"class": "standard-headline"}):
                dateText = (
                    res.parent.find("span", {"class": "standard-headline"})
                    .text.replace("Results for ", "")
                    .replace("th", "")
                    .replace("rd", "")
                    .replace("st", "")
                    .replace("nd", "")
                )

                dateArr = dateText.split()

                dateTextFromArrPadded = (
                    _padIfNeeded(dateArr[2])
                    + "-"
                    + _padIfNeeded(_monthNameToNumber(dateArr[0]))
                    + "-"
                    + _padIfNeeded(dateArr[1])
                )
                dateFromHLTV = datetime.datetime.strptime(
                    dateTextFromArrPadded, "%Y-%m-%d"
                ).replace(tzinfo=HLTV_ZONEINFO)
                dateFromHLTV = dateFromHLTV.astimezone(LOCAL_ZONEINFO)

                resultObj["date"] = dateFromHLTV.strftime("%Y-%m-%d")
            else:
                dt = datetime.date.today()
                resultObj["date"] = (
                    str(dt.day) + "/" + str(dt.month) + "/" + str(dt.year)
                )

            if res.find("td", {"class": "placeholder-text-cell"}):
                resultObj["event"] = res.find(
                    "td", {"class": "placeholder-text-cell"}
                ).text
            elif res.find("td", {"class": "event"}):
                resultObj["event"] = res.find("td", {"class": "event"}).text
            else:
                resultObj["event"] = None

            if res.find_all("td", {"class": "team-cell"}):
                resultObj["team1"] = (
                    res.find_all("td", {"class": "team-cell"})[0].text.lstrip().rstrip()
                )
                resultObj["team1score"] = converters.to_int(
                    res.find("td", {"class": "result-score"})
                    .find_all("span")[0]
                    .text.lstrip()
                    .rstrip()
                )
                resultObj["team1-id"] = _findTeamId(
                    res.find_all("td", {"class": "team-cell"})[0].text.lstrip().rstrip()
                )
                resultObj["team2"] = (
                    res.find_all("td", {"class": "team-cell"})[1].text.lstrip().rstrip()
                )
                resultObj["team2-id"] = _findTeamId(
                    res.find_all("td", {"class": "team-cell"})[1].text.lstrip().rstrip()
                )
                resultObj["team2score"] = converters.to_int(
                    res.find("td", {"class": "result-score"})
                    .find_all("span")[1]
                    .text.lstrip()
                    .rstrip()
                )
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
  
    # Get the root directory of the repository
    root_directory = os.getcwd()

    for result in results_list:
        url = result["url"]
        result_page = get_parsed_page(url)
        print("getting demo link")

        if result_page:
            demo_link_element = result_page.find('a', {'class': 'stream-box'})
            tourney_mode = result_page.find('div', {'class': 'standard-box veto-box'})
            if demo_link_element:
                demo_link = demo_link_element.get('data-demo-link')
                tourney_mode_data = tourney_mode.find("div", {"class": "padding preformatted-text"}).text
                result["demo-link"] = demo_link
                if "(Online)" in tourney_mode_data:
                    result["tourney-mode"] = "online"
                elif "(LAN)" in tourney_mode_data:
                    result["tourney-mode"] = "lan"
                event_directory = os.path.join(root_directory, result['tourney-mode'], result['event'])
            
                # Check if the event directory exists before proceeding
                if os.path.exists(event_directory):
                    # Get a list of all directories in the event directory
                    all_directories = [d for d in os.listdir(event_directory) if os.path.isdir(os.path.join(event_directory, d))]
                    # Check if any directory starts with the match ID
                    match_directory_exists = any(dir.startswith(str(result['match-id'])) for dir in all_directories)

                    if match_directory_exists:
                        print(f"A directory starting with match ID {result['match-id']} exists. Skipping...")
                        continue  # Skip to the next result
                        
                if demo_link:
                    demo_link = "https://www.hltv.org"+demo_link
                    print(demo_link)
                    download_demo_file(demo_link, result)
            else:
                result["demo-link"] = None
                result["tourney-mode"] = None
        else:
            result["demo-link"] = None
            result["tourney-mode"] = None

    return results_list


def download_demo_file(demo_link, result, api_url=FLARE_SOLVERR_URL):
    try:
        # Define headers
        headers = {"Content-Type": "application/json"}

        # Extract filename from demo link
        filename = demo_link.split("/")[-1] + ".rar"

        url_cookie = "https://hltv.org/results"

        # Data for FlareSolverr API request
        data = {
            "cmd": "request.get",
            "url": url_cookie,
            "maxTimeout": 60000
        }

        # Request to FlareSolverr API
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()

        # Extract cookies and user agent from the response
        response_data = json.loads(response.content)
        cookies = {cookie["name"]: cookie["value"] for cookie in response_data["solution"]["cookies"]}
        user_agent = response_data["solution"]["userAgent"]

        # Request the demo file with obtained cookies and user agent
        demo_file = requests.get(demo_link, cookies=cookies, headers={"User-Agent": user_agent})
        demo_file.raise_for_status()

        # Save the demo file
        with open(filename, "wb") as f:
            f.write(demo_file.content)
        print(f"Demo downloaded successfully to {filename}")

        # Create a directory for extraction if it doesn't exist
        if not os.path.exists("extracted_files"):
            os.makedirs("extracted_files")
        
        # Extract the downloaded file
        with rarfile.RarFile(filename) as rf:
            rf.extractall("extracted_files")
            extracted_files = rf.namelist()
        print(f"File extracted successfully to extracted_files/")
        # Extract the contents of the RAR archive
            
        print("Extracted files:")
        for extracted_file in extracted_files:
            print(extracted_file)

        # Parse and process the extracted files
        for file in extracted_files:
            # Assuming 'file' is the path to the extracted file
            if file.endswith('.dem') and not (file.endswith('-p1.dem') or file.endswith('-p2.dem')):
                parser = DemoParser(f"extracted_files/{file}")
                parsed_demo = Demo(file=f"extracted_files/{file}")

                # Proceed with parsing and processing
            
                print("Parsing started")

                # Testing demoparser2
                #event_df = parser.parse_event("player_death", player=["X", "Y"], other=["total_rounds_played"])
                
                # crosshair_codes
                last_tick = parser.parse_event("round_end")["tick"].to_list()[-1]
                crosshairs = parser.parse_ticks(["crosshair_code"],ticks=[last_tick])
                    
                # scoreboard
                max_tick = parser.parse_event("round_end")["tick"].max()
                wanted_fields = ["kills_total", "deaths_total", "mvps", "headshot_kills_total", "ace_rounds_total", "4k_rounds_total", "3k_rounds_total"]
                scoreboard = parser.parse_ticks(wanted_fields, ticks=[max_tick])

                #ticks_df = parser.parse_ticks(["X", "Y"])
                file_hash = compute_file_hash(f"extracted_files/{file}")
                
                kills_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/kills"
                #ticks_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/ticks"
                damages_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/damages"
                bomb_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/bombs"
                smokes_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/smokes"
                infernos_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/infernos"
                weapon_fires_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/weapon_fires"
                crosshair_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/crosshair_codes"
                scoreboard_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/scoreboard"
                adr_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/adr"
                
                print("Parsing finished")
                # Save event_df and ticks_df to JSON files
                os.makedirs(kills_output_dir, exist_ok=True)
                #os.makedirs(ticks_output_dir, exist_ok=True)
                os.makedirs(damages_output_dir, exist_ok=True)
                os.makedirs(bomb_output_dir, exist_ok=True)
                os.makedirs(smokes_output_dir, exist_ok=True)
                os.makedirs(infernos_output_dir, exist_ok=True)
                os.makedirs(weapon_fires_output_dir, exist_ok=True)
                os.makedirs(crosshair_output_dir, exist_ok=True)
                os.makedirs(scoreboard_output_dir, exist_ok=True)
                os.makedirs(adr_output_dir, exist_ok=True)

                # Testing demoparser2
                #event_df.to_json(f'{output_dir}/events.json', indent=4)
                crosshairs.to_json(f'{crosshair_output_dir}/{file_hash}.json', indent=1)
                scoreboard.to_json(f'{scoreboard_output_dir}/{file_hash}.json', indent=1)

                # Testing Awpy2
                #ticks_df.to_json(f'{ticks_output_dir}/{file_hash}.json', indent=4)
                parsed_demo.kills.to_json(f'{kills_output_dir}/{file_hash}.json', indent=1)
                parsed_demo.damages.to_json(f'{damages_output_dir}/{file_hash}.json', indent=1)
                #parsed_demo.bomb.to_json(f'{bomb_output_dir}/{file_hash}.json')
                parsed_demo.smokes.to_json(f'{smokes_output_dir}/{file_hash}.json', indent=1)
                parsed_demo.infernos.to_json(f'{infernos_output_dir}/{file_hash}.json', indent=1)
                parsed_demo.weapon_fires.to_json(f'{weapon_fires_output_dir}/{file_hash}.json', indent=1)

                # Awpy2 analytics module
                adr_match = adr(parsed_demo)
                adr_match.to_json(f'{adr_output_dir}/{file_hash}.json', indent=1)
                
                print("Parsed file saved")
                # Compress the JSON files using xz
                #subprocess.run(["xz", f"{output_dir}/events.json"])
                #subprocess.run(["xz", f"{ticks_output_dir}/{file_hash}.json"])
    
                # Execute the 'ls' command and capture the output
                #output = subprocess.check_output(['ls']).decode('utf-8')
                #print(output)
                # Delete the JSON files
                #os.remove(f'{event_output_dir}/{file_hash}.json')
                #os.remove(f'{ticks_output_dir}/{file_hash}.json')
            else:
                print(f"Ignoring file {file} because it's not a .dem file")

        # Delete the extracted files
        shutil.rmtree("extracted_files")
        print("Deleted extracted files")

        # Delete the original RAR file
        os.remove(filename)
        print(f"Deleted {filename}")

    except requests.RequestException as e:
        print(f"Error downloading demo file: {e}")

if __name__ == "__main__":
    pp = pprint.PrettyPrinter()

    pp.pprint("Results with demo links:")
    pp.pprint(get_results_with_demo_links())
