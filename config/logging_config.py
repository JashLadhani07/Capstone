#Centralized logging
# If not used, logs of different modules by different devs will be inconsistent
#logging_config makes it uniform

#It makes every log look like this:
#Timestamp | Log-level info | Origin file name | message

import logging #log levels: DEBUG/INFO/WARNING/CRITICAL/ERROR
import sys #we are going to write all the logs to stdout

#so cloud run captures them automatically
# cloud run reads stdout and sends it to google cloud logging

def setup_logging(name:str) -> logging.Logger:
    '''
    this function is called at the top of every py file
    each file will get its own logger, namespaced to that file path
    this means log lines will show which file generated them
    '''
    logger = logging.getLogger(name)
    #getLogger(name) either creates a new logger or returns an existing one
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO) #set min log level to info
    
    #handler
    handler =  logging.StreamHandler(sys.stdout)

    #Stream handler sends log lines to the stream
    formatter = logging.Formatter(
        fmt = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    #(levelname)-8s -> 8s means pad with spaces to fill 8 characters

    handler.setFormatter(formatter) #Attach formatter to handler
    #handler now knows how to format each line before printing

    logger.addHandler(handler) #Attaching handler to logger

    #FINAL FLOW OF LOGGING:
    # logger -> handler -> formatter -> stdout -> terminal
    logger.propagate = False #Controls whether log msg travel upto the root logger after being handled
    return logger
