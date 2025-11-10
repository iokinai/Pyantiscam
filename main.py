import logging
import sys

import run

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

AUDIO_FILE = None

if __name__ == '__main__':
    env = None

    if len(sys.argv) > 1:
        logging.info("Audio file passed through argv")
        env = sys.argv[1]

    run.run(env, AUDIO_FILE)
