import os
import json
import requests
import datetime
from bs4 import BeautifulSoup
import zoneinfo
import tzlocal
import converters
import pprint

HLTV_COOKIE_TIMEZONE = "Europe/Copenhagen"
HLTV_ZONEINFO = zoneinfo.ZoneInfo(HLTV_COOKIE_TIMEZONE)
LOCAL_TIMEZONE_NAME = tzlocal.get_localzone_name()
LOCAL_ZONEINFO = zoneinfo.ZoneInfo(LOCAL_TIMEZONE_NAME)

FLARE_SOLVERR_URL = "http://localhost:8191/v1"

TEAM_MAP_FOR_RESULTS = []


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


def _findTeamId(teamName: str):
    for team in TEAM_MAP_FOR_RESULTS:
        if team["name"] == teamName:
            return team["id"]
    return None


def get_results():
    results = get_parsed_page("https://www.hltv.org/results/")
    results_list = []

    pastresults = results.find_all("div", {"class": "results-holder"})
    for result in pastresults:
        resultDiv = result.find_all("div", {"class": "result-con"})
        for res in resultDiv:
            resultObj = {}
            resultObj["url"] = "https://hltv.org" + res.find("a", {"class": "a-reset"}).get("href")
            resultObj["match-id"] = converters.to_int(res.find("a", {"class": "a-reset"}).get("href").split("/")[-2])

            # Process date
            if res.parent.find("span", {"class": "standard-headline"}):
                dateText = res.parent.find("span", {"class": "standard-headline"}).text.replace("Results for ", "")
                dateText = dateText.replace("th", "").replace("rd", "").replace("st", "").replace("nd", "")
                dateArr = dateText.split()
                dateTextFromArrPadded = converters.padIfNeeded(dateArr[2]) + "-" + \
                                        converters.padIfNeeded(converters.monthNameToNumber(dateArr[0])) + "-" + \
                                        converters.padIfNeeded(dateArr[1])
                dateFromHLTV = datetime.datetime.strptime(dateTextFromArrPadded, "%Y-%m-%d").replace(tzinfo=HLTV_ZONEINFO)
                dateFromHLTV = dateFromHLTV.astimezone(LOCAL_ZONEINFO)
                resultObj["date"] = dateFromHLTV.strftime("%Y-%m-%d")
            else:
                dt = datetime.date.today()
                resultObj["date"] = f"{dt.day}/{dt.month}/{dt.year}"

            # Process event
            if res.find("td", {"class": "placeholder-text-cell"}):
                resultObj["event"] = res.find("td", {"class": "placeholder-text-cell"}).text
            elif res.find("td", {"class": "event"}):
                resultObj["event"] = res.find("td", {"class": "event"}).text
            else:
                resultObj["event"] = None

            # Process teams and scores
            if res.find_all("td", {"class": "team-cell"}):
                resultObj["team1"] = res.find_all("td", {"class": "team-cell"})[0].text.strip()
                resultObj["team1-id"] = _findTeamId(resultObj["team1"])
                resultObj["team1score"] = converters.to_int(res.find("td", {"class": "result-score"}).find_all("span")[0].text.strip())
                resultObj["team2"] = res.find_all("td", {"class": "team-cell"})[1].text.strip()
                resultObj["team2-id"] = _findTeamId(resultObj["team2"])
                resultObj["team2score"] = converters.to_int(res.find("td", {"class": "result-score"}).find_all("span")[1].text.strip())
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
            tourney_mode = result_page.find('div', {'class': 'standard-box veto-box'})
            if demo_link_element:
                demo_link = demo_link_element.get('data-demo-link')
                tourney_mode_data = tourney_mode.find("div", {"class": "padding preformatted-text"}).text
                result["demo-link"] = demo_link
                result["tourney-mode"] = "online" if "(Online)" in tourney_mode_data else "lan" if "(LAN)" in tourney_mode_data else None
                if demo_link:
                    demo_link = "https://www.hltv.org" + demo_link
                    download_extract_compress(demo_link)
            else:
                result["demo-link"] = None
                result["tourney-mode"] = None
        else:
            result["demo-link"] = None
            result["tourney-mode"] = None

    return results_list


def download_extract_compress(demo_link):
    api_url = "http://localhost:8191/v1"
    headers = {"Content-Type": "application/json"}

    data = {
        "cmd": "request.get",
        "url": demo_link,
        "maxTimeout": 60000
    }

    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        cookies = {cookie["name"]: cookie["value"] for cookie in response_data["solution"]["cookies"]}
        user_agent = response_data["solution"]["userAgent"]
        demo_file = requests.get(demo_link, cookies=cookies, headers={"User-Agent": user_agent})
        if demo_file.status_code == 200:
            filename = demo_link.split("/")[-1] + ".rar"
            with open(filename, "wb") as f:
                f.write(demo_file.content)
            print(f"Demo downloaded successfully to {filename}")
        else:
            print("Failed to download the demo file
