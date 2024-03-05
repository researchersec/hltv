import requests
from bs4 import BeautifulSoup
import zoneinfo
import tzlocal
import datetime
from python_utils import converters
import pprint

HLTV_COOKIE_TIMEZONE = "Europe/Copenhagen"
HLTV_ZONEINFO = zoneinfo.ZoneInfo(HLTV_COOKIE_TIMEZONE)
LOCAL_TIMEZONE_NAME = tzlocal.get_localzone_name()
LOCAL_ZONEINFO = zoneinfo.ZoneInfo(LOCAL_TIMEZONE_NAME)

FLARE_SOLVERR_URL = "http://localhost:8191/v1"  # FlareSolverr URL

TEAM_MAP_FOR_RESULTS = []

def get_parsed_page(url):
    # This fixes a blocked by cloudflare error i've encountered
    headers = {
        "referer": "https://www.hltv.org/stats",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    cookies = {"hltvTimeZone": HLTV_COOKIE_TIMEZONE}

    # Request data through FlareSolverr
    post_body = {"cmd": "request.get", "url": url, "maxTimeout": 60000}

    response = requests.post(
        FLARE_SOLVERR_URL, headers={"Content-Type": "application/json"}, json=post_body
    )

    if response.status_code == 200:
        json_response = response.json()
        if json_response.get("status") == "ok":
            html = json_response["solution"]["response"]
            return BeautifulSoup(html, "lxml")

    # If FlareSolverr fails or encounters an issue, return None
    return None

def _get_all_teams():
    if not TEAM_MAP_FOR_RESULTS:
        teams = get_parsed_page("https://www.hltv.org/stats/teams?minMapCount=0")
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

        if result_page:
            demo_link_element = result_page.find('a', {'class': 'stream-box'})
            if demo_link_element:
                demo_link = demo_link_element.get('data-demo-link')
                result["demo-link"] = demo_link
            else:
                result["demo-link"] = None
        else:
            result["demo-link"] = None

    return results_list

if __name__ == "__main__":
    pp = pprint.PrettyPrinter()

    pp.pprint("Results with demo links:")
    pp.pprint(get_results_with_demo_links())
