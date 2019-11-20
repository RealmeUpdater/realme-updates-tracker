#!/usr/bin/env python3.7
"""Realme Updates Tracker"""
from datetime import datetime
from glob import glob
from os import environ, system, rename

import yaml
from bs4 import BeautifulSoup
from requests import get, post

# Setup variables
BOT_TOKEN = environ["realme_tg_bot_token"]
CHAT = "@RealmeUpdatesTracker"
GIT_OAUTH_TOKEN = environ['GIT_TOKEN']

# Tracked downloads pages
URLS = ["https://www.realme.com/in/support/software-update",
        "https://www.realme.com/cn/support/software-update",
        "https://www.realme.com/eu/support/software-update",
        "https://www.realme.com/ru/support/software-update"]

DEVICES = {}
REGIONS = []

def update_device(codename: str, device: str):
    try:
        if DEVICES[codename] and device not in DEVICES[codename].split('/'):
            DEVICES.update({codename: f"{DEVICES[codename]}/{device}"})
    except KeyError:
        DEVICES.update({codename: device})


def get_downloads_html(url: str) -> list:
    """
    Scrap downloads info from the website
    :param url: realme downloads page
    :return: list of devices latest downloads HTML
    """
    downloads_html = BeautifulSoup(get(url).text, "html.parser") \
        .select_one("div.software-items").select("div.software-item")
    return downloads_html


def parse_html(html: list) -> list:
    """
    Parse each device HTML into a list of dictionaries
    :param html: list of devices downloads HTML
    :return: a list of latest devices' updates
    """
    updates = []
    for item in html:
        title_tag = item.select_one("h3.software-mobile-title")
        title = title_tag.text.strip().replace('  ', ' ')
        region = set_region(title_tag.a["href"])
        _system = item.select_one("div.software-system").text.strip()
        codename = ""
        try:
            version = item.select("div.software-field")[0].text.strip().split(" ")[1]
            codename = version.split('_')[0]
        except IndexError:
            version = "Unknown"
        try:
            date = item.select("div.software-field")[1].text.strip().split(": ")[1].strip()
            if len(date.split('/')[0]) == 4:
                date = datetime.strptime(date, "%Y/%m/%d").strftime("%d/%m/%Y")
        except IndexError:
            date = "Unknown"
        size = item.select("div.software-field")[2].span.text.strip().replace(' ', '')
        if size.endswith('G'):
            size = size.replace('G', 'GB')
        try:
            md5 = item.select("div.software-field")[3].text.strip().split(": ")[1]
        except IndexError:
            md5 = "Unknown"
        download = item.select_one("div.software-download").select_one(
            "a.software-button")["data-href"]
        changelog = item.select_one("div.software-log").get_text("\n", strip=True)
        changelog_text = ""
        for line in changelog.splitlines():
            if line.startswith('●') or line.startswith('*'):
                changelog_text += f"{line}\n"
            else:
                changelog_text += f"**{line}**:\n"
        update = {
            "device": title,
            "codename": codename,
            "region": region,
            "system": _system,
            "version": version,
            "date": date,
            "size": size,
            "md5": md5,
            "download": download,
            "changelog": changelog_text
        }
        if download:
            write_yaml(update, f"{region}/{codename}.yml")
        updates.append(update)
        update_device(codename, title)
    return updates


def set_region(url: str) -> str:
    """
    Set the region based on the url
    :param url: realme website url
    :return: region string
    """
    if "in" in url:
        return "India"
    elif "eu" in url:
        return "Europe"
    elif "ru" in url:
        return "Russia"
    else:
        return "China"


def write_yaml(downloads, filename: str):
    """
    Write updates list to yaml file
    :param downloads: list of dictionaries of updates
    :param filename: output file name
    :return:
    """
    def str_presenter(dumper, data):
        # https://stackoverflow.com/a/33300001
        if len(data.splitlines()) > 1:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
    yaml.add_representer(str, str_presenter)

    with open(f"{filename}", 'w') as out:
        yaml.dump(downloads, out, allow_unicode=True)


def merge_yaml():
    """
    merge all regions yaml files into one file
    """
    yaml_files = [set_region(x) for x in URLS]
    yaml_data = []
    for file in yaml_files:
        with open(f"{file}/{file}.yml", "r") as yaml_file:
            updates = yaml.load(yaml_file, Loader=yaml.FullLoader)
            for update in updates:
                yaml_data.append(update)
    with open(f'latest.yml', "w") as output:
        yaml.dump(yaml_data, output, allow_unicode=True)


def merge_archive():
    """
    merge all archive yaml files into one file
    """
    yaml_files = [x for x in sorted(glob(f'archive/*.yml'))
                  if not x.endswith('archive.yml')]
    yaml_data = []
    for file in yaml_files:
        with open(file, "r") as yaml_file:
            yaml_data.append(yaml.load(yaml_file, Loader=yaml.FullLoader))
    with open('archive/archive.yml', "w") as output:
        yaml.dump(yaml_data, output, allow_unicode=True)


def diff_yaml(filename: str) -> list:
    """
    Compare old and new yaml files to get the new updates
    :param filename: updates file
    :return: list of dictionaries of new updates
    """
    try:
        with open(f'{filename}/{filename}.yml', 'r') as new, \
                open(f'{filename}/old_{filename}', 'r') as old_data:
            latest = yaml.load(new, Loader=yaml.FullLoader)
            old = yaml.load(old_data, Loader=yaml.FullLoader)
            first_run = False
    except FileNotFoundError:
        print(f"Can't find old {filename} files, skipping")
        first_run = True
    if first_run is False:
        if len(latest) == len(old):
            return [new_ for new_, old_ in zip(latest, old)
                    if not new_['version'] == old_['version']]
        old_codenames = [i["codename"] for i in old]
        new_codenames = [i["codename"] for i in latest]
        changes = [i for i in new_codenames if i not in old_codenames]
        if changes:
            return [i for i in latest for codename in changes
                    if codename == i["codename"]]


def generate_message(update: dict) -> str:
    """
    generates telegram message from update dictionary
    :return: message string
    """
    device = update["device"]
    codename = update["codename"]
    _system = update["system"]
    region = update["region"]
    version = update["version"]
    date = update["date"]
    size = update["size"]
    md5 = update["md5"]
    download = update["download"]
    changelog = update["changelog"]
    message = f"New update available!\n"
    message += f"*Device:* {device} \n" \
               f"*Codename:* #{codename} \n" \
               f"*Region:* {region} \n" \
               f"*System:* {_system} \n" \
               f"*Version:* `{version}` \n" \
               f"*Release Date:* {date} \n" \
               f"*Size*: {size} \n" \
               f"*MD5*: `{md5}`\n" \
               f"*Download*: [Here]({download})\n" \
               f"*Changelog*: ```\n{changelog}\n```\n" \
               "@RealmeUpdatesTracker"
    return message


def tg_post(message: str) -> int:
    """
    post message to telegram
    :return: post request status code
    """
    params = (
        ('chat_id', CHAT),
        ('text', message),
        ('parse_mode', "Markdown"),
        ('disable_web_page_preview', "yes")
    )
    telegram_url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    telegram_req = post(telegram_url, params=params)
    telegram_status = telegram_req.status_code
    if telegram_status == 200:
        pass
    elif telegram_status == 400:
        print("Bad recipient / Wrong text format")
    elif telegram_status == 401:
        print("Wrong / Unauthorized token")
    else:
        print("Unknown error")
        print("Response: " + telegram_req.reason)
    return telegram_status


def archive(update: dict):
    """Append new update to the archive"""
    link = update['download']
    version = update['version']
    codename = link.split('/')[-1].split('_')[0]
    try:
        with open(f'archive/{codename}.yml', 'r') as yaml_file:
            data = yaml.load(yaml_file, Loader=yaml.FullLoader)
            data[codename].update({version: link})
            data.update({codename: data[codename]})
            with open(f'archive/{codename}.yml', 'w') as output:
                yaml.dump(data, output, allow_unicode=True)
    except FileNotFoundError:
        data = {codename: {version: link}}
        with open(f'archive/{codename}.yml', 'w') as output:
            yaml.dump(data, output, allow_unicode=True)


def git_commit_push():
    """
    git add - git commit - git push
    """
    today = str(datetime.today()).split('.')[0]
    system("git add *.yml */*.yml && git -c \"user.name=RealmeCI\" -c "
           "\"user.email=RealmeCI@example.com\" "
           "commit -m \"sync: {}\" && "" \
           ""git push -q https://{}@github.com/androidtrackers/"
           "realme-updates-tracker.git HEAD:master"
           .format(today, GIT_OAUTH_TOKEN))


def main():
    """
    Realme updates scraper and tracker
    """
    for url in URLS:
        region = set_region(url)
        REGIONS.append(region)
        rename(f'{region}/{region}.yml', f'{region}/old_{region}')
        downloads_html = get_downloads_html(url)
        updates = parse_html(downloads_html)
        write_yaml(updates, f"{region}/{region}.yml")
    merge_yaml()
    for region in REGIONS:
        changes = diff_yaml(region)
        if changes:
            for update in changes:
                if not update["version"]:
                    continue
                message = generate_message(update)
                # print(message)
                status = tg_post(message)
                if status == 200:
                    print(f"{update['device']}: Telegram Message sent successfully")
                archive(update)
        else:
            print(f"{region}: No new updates.")
    merge_archive()
    write_yaml(DEVICES, "devices.yml")
    write_yaml(REGIONS, "regions.yml")
    git_commit_push()


if __name__ == '__main__':
    main()
