import ctypes
from ctypes import c_void_p, c_short, c_int, POINTER, Structure

# Load the Toshiba Voice Trigger library
toshiba_vt = ctypes.CDLL('./libVT_ARML64h.so')  

# Define the necessary structures and enums
class VTAPIHandle(Structure):
    pass

class VTAPI_ParameterID(ctypes.c_int):
    VTAPI_ParameterID_aThreshold = 0
    VTAPI_ParameterID_silDiscount = 2
    VTAPI_ParameterID_frameSkip = 8

# Define function prototypes
toshiba_vt.VTAPI_info.argtypes = [c_void_p, POINTER(c_int), POINTER(c_short), POINTER(c_short), POINTER(c_short)]
toshiba_vt.VTAPI_info.restype = c_short

toshiba_vt.VTAPI_open.argtypes = [c_void_p, c_void_p, POINTER(POINTER(VTAPIHandle))]
toshiba_vt.VTAPI_open.restype = c_short

toshiba_vt.VTAPI_process.argtypes = [POINTER(VTAPIHandle), POINTER(c_short), POINTER(c_short)]
toshiba_vt.VTAPI_process.restype = c_short

toshiba_vt.VTAPI_setParameter.argtypes = [POINTER(VTAPIHandle), VTAPI_ParameterID, c_short, c_short]
toshiba_vt.VTAPI_setParameter.restype = c_short

toshiba_vt.VTAPI_getParameter.argtypes = [POINTER(VTAPIHandle), VTAPI_ParameterID, c_short, POINTER(c_short)]
toshiba_vt.VTAPI_getParameter.restype = c_short

class ToshibaVoiceTrigger:
    def __init__(self, vtdic_path):
        self.vtdic = self._load_vtdic(vtdic_path)
        self.heap_size, self.frame_size, self.latency, self.num_keywords = self._get_info()
        self.heap = ctypes.create_string_buffer(self.heap_size)
        self.vtapi = POINTER(VTAPIHandle)()
        self._open()

    def _load_vtdic(self, path):
        with open(path, 'rb') as f:
            return f.read()

    def _get_info(self):
        heap_size = c_int()
        frame_size = c_short()
        latency = c_short()
        num_keywords = c_short()
        result = toshiba_vt.VTAPI_info(self.vtdic, ctypes.byref(heap_size), ctypes.byref(frame_size), 
                                       ctypes.byref(latency), ctypes.byref(num_keywords))
        if result != 0:
            raise Exception(f"VTAPI_info failed with error code {result}")
        return heap_size.value, frame_size.value, latency.value, num_keywords.value

    def _open(self):
        result = toshiba_vt.VTAPI_open(self.vtdic, self.heap, ctypes.byref(self.vtapi))
        if result != 0:
            raise Exception(f"VTAPI_open failed with error code {result}")

    def set_parameter(self, parameter_id, keyword_id, value):
        result = toshiba_vt.VTAPI_setParameter(self.vtapi, VTAPI_ParameterID(parameter_id), keyword_id, value)
        if result != 0:
            raise Exception(f"VTAPI_setParameter failed with error code {result}")

    def get_parameter(self, parameter_id, keyword_id):
        value = c_short()
        result = toshiba_vt.VTAPI_getParameter(self.vtapi, VTAPI_ParameterID(parameter_id), keyword_id, ctypes.byref(value))
        if result != 0:
            raise Exception(f"VTAPI_getParameter failed with error code {result}")
        return value.value

    def process(self, frame):
        detections = (c_short * self.num_keywords)()
        result = toshiba_vt.VTAPI_process(self.vtapi, frame.ctypes.data_as(POINTER(c_short)), detections)
        if result != 0:
            raise Exception(f"VTAPI_process failed with error code {result}")
        return list(detections)