import pvporcupine 
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PicoVoiceTrigger:
    def __init__(self, args):
        self.porcupine = self._create_porcupine(args.access_key, args.model_path, args.keyword_paths, args.sensitivities)

    def _create_porcupine(self,access_key, model_path, keyword_paths, sensitivities):
        try:
            return pvporcupine.create(
                access_key=access_key,
                model_path=model_path,
                keyword_paths=keyword_paths,
                sensitivities=sensitivities)
        except pvporcupine.PorcupineInvalidArgumentError as e:
            logger.info("One or more arguments provided to Porcupine is invalid: ", e)
            raise e
        except pvporcupine.PorcupineActivationError as e:
            logger.info("AccessKey activation error")
            raise e
        except pvporcupine.PorcupineActivationLimitError as e:
            logger.info("AccessKey '%s' has reached its temporary device limit" % access_key)
            raise e
        except pvporcupine.PorcupineActivationRefusedError as e:
            logger.info("AccessKey '%s' refused" % access_key)
            raise e
        except pvporcupine.PorcupineActivationThrottledError as e:
            logger.info("AccessKey '%s' has been throttled" % access_key)
            raise e
        except pvporcupine.PorcupineError as e:
            logger.info(f"Failed to initialize Porcupine: {e}")
            raise e
    
    def getPico(self):
        return self.porcupine