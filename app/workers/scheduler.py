from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def check_bus_arrivals():
    print("Checking ETA...")  # replace with real logic

scheduler.add_job(check_bus_arrivals, "interval", seconds=30)

def start_scheduler():
    scheduler.start()