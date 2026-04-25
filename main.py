import asyncio
import signal
import logging
import time

from emotionengine import EmotionEngine
from subsystems.TailController import TailController
from subsystems.E4Controller import E4Controller

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
running = True


# clean shutdown stuff
def handle_shutdown(sig, frame):
    global running
    logger.info("shutdown signal received, stopping...")
    running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def cleanup(tail, e4):
    logger.info("resetting and disengaging tail...")
    tail.cleanup()
    logger.info("disconnecting e4...")
    e4.end()

async def stress_loop(ee):
    while running:
        ee.update_stress()
        await asyncio.sleep(0.250)

async def tail_loop(tail, ee):
    t = time.monotonic()
    while running:
        dt = time.monotonic() - t
        x = ee.map(dt)
        tail.move_to(x, 0)
        await asyncio.sleep(0.100)

async def main():
    logger.info("welcome to nekolink. initializing...")

    tail = TailController(0, 2, 4)
    ee = EmotionEngine()
    e4 = E4Controller()

    logger.info("attempting to connect to e4...")
    if not await e4.connect(ee.bvp_parser(), ee.eda_parser(), ee.acc_parser()):
        logger.error("couldn't connect to e4, quitting...")
        return

    logger.info("e4 connected successfully.")

    logger.info("tail calibration and reset...")
    tail.calibrate()

    logger.info("beginning emotion calibration...")
    # logger.info("beginning emotion calibration. this will measure your baseline stress level.")
    # logger.info("please remain calm and avoid any movements or distressing thoughts for 60 seconds.")
    await ee.calibrate()
    await e4.start()
    logger.info("done.")

    logger.info("all systems ready. starting nekolink...")
    try:
        await asyncio.gather(stress_loop(ee), tail_loop(tail, ee))
    finally:
        cleanup(tail, e4)

if __name__ == "__main__":
    asyncio.run(main())