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
    results = get_parsed_page("https://www.hltv.org/results/")

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
                # Check if the demo directory exists in the repository using the match-id
                demo_directory = os.path.join(os.getcwd(), result['tourney-mode'], result['event'], f"{result['match-id']}")
                if os.path.exists(demo_directory):
                    # If demo directory exists, print message and continue to the next result
                    print(f"Demo for match {result['match-id']} already saved. Skipping.")
                    continue
                # Download, extract, and compress the demo file
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
            if file.endswith('.dem'):
                parser = DemoParser(f"extracted_files/{file}")
                # Proceed with parsing and processing
            
                print("Parsing started")
                event_df = parser.parse_event("player_death", player=["X", "Y"], other=["total_rounds_played"])
                #ticks_df = parser.parse_ticks(["X", "Y"])
                file_hash = compute_file_hash(f"extracted_files/{file}")
                event_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/events"
                #ticks_output_dir = f"{result['tourney-mode']}/{result['event']}/{result['match-id']}-{result['team1']}-vs-{result['team2']}/ticks"
    
                print("Parsing finished")
                # Save event_df and ticks_df to JSON files
                os.makedirs(event_output_dir, exist_ok=True)
                #os.makedirs(ticks_output_dir, exist_ok=True)
                event_df.to_json(f'{event_output_dir}/{file_hash}.json', indent=4)
                #ticks_df.to_json(f'{ticks_output_dir}/{file_hash}.json', indent=4)
    
                print("Parsed file saved")
                # Compress the JSON files using xz
                subprocess.run(["xz", f"{event_output_dir}/{file_hash}.json"])
                #subprocess.run(["xz", f"{ticks_output_dir}/{file_hash}.json"])
    
                # Execute the 'ls' command and capture the output
                output = subprocess.check_output(['ls']).decode('utf-8')
                print(output)
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
