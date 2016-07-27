__author__ = 'florianseidl'

import sys
import os
import logging

# append module root directory to sys.path
sys.path.append(
    os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    , "src")
)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
