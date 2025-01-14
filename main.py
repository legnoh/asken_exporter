import logging, os, time, sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from prometheus_client import CollectorRegistry, Gauge, Info, start_http_server
from pyvirtualdisplay import Display
import modules.asken as asken

log_format = '%(asctime)s[%(filename)s:%(lineno)d][%(levelname)s] %(message)s'
log_level = os.getenv("LOGLEVEL", logging.INFO)
logging.basicConfig(format=log_format, datefmt='%Y-%m-%d %H:%M:%S%z', level=log_level)

if __name__ == '__main__':

    logging.info("initializing exporter...")
    registry = CollectorRegistry()
    start_http_server(int(os.environ.get('PORT', 8000)), registry=registry)

    logging.info("# initializing chromium options...")
    options = webdriver.ChromeOptions()
    options.add_argument("--user-data-dir=/tmp/asken-exporter/userdata")

    today = time.strftime("%Y-%m-%d")

    metrics = {
        "daily": {},
        "weekly": {},
        "monthly": {},
    }

    advice_targets = [
        { 'name': 'daily', 'path': '/0', 'desc': '1日分' },
        { 'name': 'weekly', 'path': '/1', 'desc': '過去7日の平均' },
        { 'name': 'monthly', 'path': '/2', 'desc': '月平均' },
    ]

    # create metrics
    logging.info("# create metrics instances...")
    score_gauge = Gauge("asken_score", "あすけん > 健康度", registry=registry)
    for target in advice_targets:
        metrics[target['name']]['advice'] = Info(
            "asken_{n}_advice".format(n=target['name']),
            "あすけん > アドバイス > {d}".format(d=target['desc']),
            registry=registry
        )
        metrics[target['name']]['detail_advice'] = Info(
            "asken_{n}_detail_advice".format(n=target['name']),
            "あすけん > 栄養価アドバイス > {d}".format(d=target['desc']),
            registry=registry
        )

    while True:

        if os.path.isfile("/.dockerenv"):
            logging.info("# start display...")
            display = Display(visible=0, size=(1024, 768))
            display.start()
        
        logging.info("# start selenium...")
        driver = webdriver.Chrome(service=Service(), options=options)
        driver.implicitly_wait(0.5)

        logging.info("# login to asken...")
        username = os.environ['ASKEN_USERNAME']
        password = os.environ['ASKEN_PASSWORD']
        driver = asken.login(driver, username, password)
        if driver == None:
            sys.exit(1)

        logging.info("# checking asken premium...")
        premium = asken.is_premium(driver)

        logging.info("# getting daily score...")
        daily_score = asken.get_latest_daily_score(driver)
        score_gauge.set(daily_score)

        logging.info("# getting advices...")
        for target in advice_targets:
            advice = asken.get_advice(driver, target['path'], premium)
            metrics[target['name']]['advice'].info( { "advice": advice } )

            detail_advice = asken.get_detail_advice(driver)
            metrics[target['name']]['detail_advice'].info( { "advice": detail_advice } )

        logging.info("# scraping account is successfully.")
        driver.quit()
        if os.path.isfile("/.dockerenv"):
            display.stop()
        time.sleep(3600*4)
