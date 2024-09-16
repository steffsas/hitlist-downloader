import time
import httpx
import os
import lzma
import re
import pandas as pd
import logging
import sys
import schedule

from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ipaddress import ip_address, IPv6Address

URL_ENV = "URL"
LOG_FOLDER_ENV = "LOG_FOLDER"
DOWNLOAD_FOLDER_ENV = "DOWNLOAD_FOLDER"
OUTPUT_FOLDER_ENV = "OUTPUT_FOLDER"
SCHEDULE_ENV = "SCHEDULE"
SCHEDULE_DAILY_AT_ENV = "SCHEDULE_DAILY_AT"

DEFAULT_SCHEDULE_TIME = "00:30:00"
DEFAULT_LOG_FOLDER = "logs"

logger = logging.getLogger(__name__)

def main() -> None:
    # set logger config
    prepareLogger()

    # let's load the .env variables
    load_dotenv(".env", override=False)

    logger.info("start")

    shouldSchedule = os.getenv(SCHEDULE_ENV)
    if shouldSchedule == None or shouldSchedule.lower() != "true":
        download()
        return

    scheduleDailyAt = os.getenv(SCHEDULE_DAILY_AT_ENV)
    if scheduleDailyAt == None:
        logger.warning(f"no schedule time found, fallback to schedule at {DEFAULT_SCHEDULE_TIME} every day")
        scheduleDailyAt = DEFAULT_SCHEDULE_TIME

    logger.info(f"start scheduling download daily at {scheduleDailyAt}")

    # let's schedule the download every day at the specified time
    schedule.every().day.at(scheduleDailyAt).do(download)

    while True:
        schedule.run_pending()
        time.sleep(1)

def download():
    logging.info("start download")

    today = datetime.now().strftime("%Y-%m-%d")

    url = os.getenv(URL_ENV)
    if url == None:
        logger.error("URL not found in environment variables")
        return

    downloadFolder = os.getenv(DOWNLOAD_FOLDER_ENV)
    outputFolder = os.getenv(OUTPUT_FOLDER_ENV)

    if not os.path.exists(downloadFolder):
        os.makedirs(downloadFolder)

    if not os.path.exists(outputFolder):
        os.makedirs(outputFolder)

    soup = receiveSoup(url)
    outputLinks = getSortedLinks(soup)
    if len(outputLinks) == 0:
        logger.error("no links found")
        return
    
    # let's receive all outputs from the latest link
    outputLink = outputLinks[0][1]
    soup = receiveSoup(f"{url}/{outputLink}")
    if soup == None:
        return
    fileLinks = getSortedLinks(soup)
    if len(fileLinks) == 0:
        if len(outputLinks) == 1:
            logger.error("no links found")
            return
        
        # let's try the second latest link
        outputLink = outputLinks[1][1]
        soup = receiveSoup(f"{url}/{outputLink}")
        if soup == None:
            return
        fileLinks = getSortedLinks(soup)
        if len(fileLinks) == 0:
            logger.error("no links found")
            return
        
    # let's search for UDP links
    fileLink = ""
    for link, text in fileLinks:
        if "udp53" in text.lower():
            fileLink = link
            break
    else:
        logger.error("no udp53 link found")
        return

    # let's download the file
    downloadLink = f"{url}/{outputLink}{fileLink}"

    # let's get the date from the filename
    date = extractDateFromFilename(fileLink)
    if date == "":
        logger.info("date not found in filename, will use date ", today)
        date = today

    downloadedFile = f"{downloadFolder}/ipv6-udp-{date}.xz"

    if os.path.exists(downloadedFile):
        logger.warning("file already downloaded, exiting")
        return

    logger.info(f"download file: {fileLink}")
    r = httpx.get(downloadLink, follow_redirects=True)
    with open(downloadedFile, 'wb') as f:
        f.write(r.content)
    logger.info(f"file downloaded and written to {downloadedFile}")
    outputFile = f"{downloadFolder}/ipv6-udp-{date}.csv"
    
    # extract file with xz
    logger.info(f"extract {downloadedFile} file to {outputFile}")
    try:
        with lzma.open(downloadedFile, "rb") as f:
            fileContent = f.read()
        with open(outputFile, "wb") as f:
            f.write(fileContent)
        logger.info("file extracted")
    except Exception as e:
        logger.info("failed to extract file: ", e)

    # let's parse the downloaded csv
    ips = pd.read_csv(outputFile)
    outputTxt = f"{outputFolder}/ipv6-udp-{date}.txt"

    # let's prepare the columns, add column names if necessary
    ips = prepareColumns(ips)

    logger.info("got {0} ips, removing duplicates...".format(len(ips)))

    ips = ips[(ips["success"] == 1) | (ips["success"] == "1")][
        # for some reason saddr is the original destination
        ["saddr"]
    ].drop_duplicates(ignore_index=True, inplace=False)

    logger.info("will write {0} ips to {1}".format(len(ips), outputTxt))

    with open(outputTxt, "w") as f:
        for index, row in ips.iterrows():
            f.write(row["saddr"] + "\n")

    logger.info("done")

def prepareLogger():
    today = datetime.now().strftime("%Y-%m-%d")

    logFolder = os.getenv(LOG_FOLDER_ENV)
    if logFolder == None:
        logFolder = DEFAULT_LOG_FOLDER

    # create log folder if not exists
    if not os.path.exists(logFolder):
        os.makedirs(logFolder)

    logFileName = f"{logFolder}/{today}.log"

    # create log file if not exists
    Path(logFileName).touch()

    file_handler = logging.FileHandler(filename=logFileName)
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    handlers = [file_handler, stdout_handler]

    logging.basicConfig(
        handlers=handlers,
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    )

def receiveSoup(url: str) -> BeautifulSoup:
    response = httpx.get(url, follow_redirects=True)
    if response.status_code != 200:
        logger.error(f"failed to get page, status code {response.status_code}")
        return None
    return BeautifulSoup(response.text, "html.parser")

def getSortedLinks(soup: BeautifulSoup) -> list[tuple[str, str]]:
    # let's get all the links
    links = []
    for a in soup.find_all('a', href=True):
        if a.get_text() == "." or a.get_text() == ".." or a.get_text() == "../"  or a.get_text() == "./":
            continue
        links.append((a["href"], a.get_text()))
    
    # let's get the latest link
    sortedLinks = sorted(links, key=lambda x: x[1], reverse=True)
    return sortedLinks

def extractDateFromFilename(filename: str) -> str:
    # Define the regular expression pattern to match YYYY-MM-DD format
    pattern = r"(\d{4}-\d{2}-\d{2})"

    # Use re.search to find the match
    match = re.search(pattern, filename)

    if match:
        # Extract the date if there's a match
        date = match.group(1)
        return date
    else:
        logger.error("no date found in filename")
        return ""

def prepareColumns(df: pd.DataFrame) -> pd.DataFrame:
    DEFAULT_COLUMN_LEN = 13

    if "success" not in df.columns or "saddr" not in df.columns:
        ipv6_dest = df.columns[0]
        success = df.columns[-1]

        # check whether entry is an ipv6 address
        if isIpv6(ipv6_dest) and (success == "1" or success == 1):
            logger.info("indicated header as valid hit, let's add it to the dataframe...")
            df.loc[len(df)] = [col for col in df.columns]

        if len(df.columns) == DEFAULT_COLUMN_LEN:
            df.columns = ['saddr', 'daddr', 'ipid', 'ttl', 'sport', 'dport', 'classification',
                'repeat', 'cooldown', 'timestamp_ts', 'timestamp_us', 'data',
                'success']
        else:
            # we define the last column as the success column
            # and the first column as the ip address
            cols = [f"col{i}" for i in range(len(df.columns))]
            cols[0] = "saddr"
            cols[-1] = "success"

            df.columns = cols
    return df

def isIpv6(addr: str) -> bool:
    try:
        addr = ip_address(addr)
        if type(addr) is IPv6Address:
            return True
        return False
    except ValueError:
        return False

if __name__ == "__main__":
    main()