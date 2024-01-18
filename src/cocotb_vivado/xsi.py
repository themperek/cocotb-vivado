import ctypes
from functools import lru_cache


class XSI:
    xsiNumTopPorts = 1
    xsiTimePrecisionKernel = 2
    xsiDirectionTopPort = 3
    xsiHDLValueSize = 4
    xsiNameTopPort = 5

    status = {1: "xsiNormal", 2: "xsiError", 3: "xsiFatalError"}

    class xsi_setup_info(ctypes.Structure):
        _fields_ = [
            ("logFileName", ctypes.c_char_p),
            ("wdbFileName", ctypes.c_char_p),
        ]

    class s_xsi_vlog_logicval(ctypes.Structure):
        _fields_ = [
            ("aVal", ctypes.c_uint32),
            ("bVal", ctypes.c_uint32),
        ]

    def __init__(self, xsim_design, tracefile=None):
        self.xsi_lib = ctypes.cdll.LoadLibrary(xsim_design)
        self.init_func_definitions()

        self.xsi_handle = self.open()

        if tracefile is not None:
            self.xsi_lib.xsi_trace_all(self.xsi_handle)

    def init_func_definitions(self):
        self.xsi_lib.xsi_open.restype = ctypes.c_void_p
        self.xsi_lib.xsi_open.argtypes = [ctypes.POINTER(XSI.xsi_setup_info)]

        self.xsi_lib.xsi_close.argtypes = [ctypes.c_void_p]

        self.xsi_lib.xsi_get_int.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.xsi_lib.xsi_get_int.restype = ctypes.c_int

        self.xsi_lib.xsi_get_time.argtypes = [ctypes.c_void_p]
        self.xsi_lib.xsi_get_time.restype = ctypes.c_uint64

        self.xsi_lib.xsi_run.argtypes = [ctypes.c_void_p, ctypes.c_uint64]

        self.xsi_lib.xsi_get_port_number.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.xsi_lib.xsi_get_port_number.restype = ctypes.c_int32

        self.xsi_lib.xsi_get_str_port.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.xsi_lib.xsi_get_str_port.restype = ctypes.c_char_p

        self.xsi_lib.xsi_get_int_port.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.xsi_lib.xsi_get_int_port.restype = ctypes.c_int

        self.xsi_lib.xsi_trace_all.argtypes = [ctypes.c_void_p]

        self.xsi_lib.xsi_get_value.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.c_void_p,
        ]
        self.xsi_lib.xsi_put_value.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.c_void_p,
        ]

        self.xsi_lib.xsi_get_error_info.argtypes = [ctypes.c_void_p]
        self.xsi_lib.xsi_get_error_info.restype = ctypes.c_char_p

        self.xsi_lib.xsi_get_status.argtypes = [ctypes.c_void_p]
        self.xsi_lib.xsi_get_status.restype = ctypes.c_int32

    def open(self, wdb_file="xsi.wdb", log="xsi.log"):
        info = XSI.xsi_setup_info(logFileName=log.encode("utf-8"), wdbFileName=wdb_file.encode("utf-8"))
        return self.xsi_lib.xsi_open(ctypes.byref(info))

    @lru_cache(maxsize=None)
    def get_port_name(self, port_id):
        return self.xsi_lib.xsi_get_str_port(self.xsi_handle, port_id, XSI.xsiNameTopPort).decode("utf-8")

    def put_value(self, port_id, value):
        vlog_val = self._binstr_to_vlog_logicval(value)
        self.xsi_lib.xsi_put_value(self.xsi_handle, port_id, vlog_val)

    @lru_cache(maxsize=None)
    def _binstr_to_vlog_logicval(self, value):
        size = len(value)
        vlog_val = (XSI.s_xsi_vlog_logicval * ((size // 32) + 1))()

        i = 0
        for v in value[::-1]:
            si = i // 32
            bi = i % 32
            # 0=00, 1=10, X=11, Z=01
            if v == "1":
                vlog_val[si].aVal |= 0x1 << bi
            elif v == "X" or v == "x":
                vlog_val[si].aVal |= 0x1 << bi
                vlog_val[si].bVal |= 0x1 << bi
            elif v == "z" or v == "Z":
                vlog_val[si].bVal |= 0x1 << bi

            i += 1

        return vlog_val

    def get_value(self, port_id):
        size = self.get_port_size(port_id)
        vlog_val = (XSI.s_xsi_vlog_logicval * ((size // 32) + 1))()
        self.xsi_lib.xsi_get_value(self.xsi_handle, port_id, vlog_val)
        return self._vlog_logicval_binstr_to(vlog_val, size)

    def _vlog_logicval_binstr_to(self, vlog_val, size):
        value = ["0"] * size

        i = 0
        for _ in range(size):
            si = i // 32
            bi = i % 32

            # 0=00, 1=10, X=11, Z=01
            b_a = (vlog_val[si].aVal & (0x1 << bi)) > 0
            b_b = (vlog_val[si].bVal & (0x1 << bi)) > 0

            b_val = "0"
            if b_a == True and b_b == False:
                b_val = "1"
            elif b_a == True and b_b == True:
                b_val = "x"
            elif b_a == False and b_b == True:
                b_val = "z"

            value[size - 1 - i] = b_val

            i += 1

        return "".join(value)

    @lru_cache(maxsize=None)
    def get_port_size(self, port_id):
        return self.xsi_lib.xsi_get_int_port(self.xsi_handle, port_id, XSI.xsiHDLValueSize)

    def get_precision(self):
        return self.xsi_lib.xsi_get_int(self.xsi_handle, XSI.xsiTimePrecisionKernel)

    def ports_number(self):
        return self.xsi_lib.xsi_get_int(self.xsi_handle, XSI.xsiNumTopPorts)

    def get_time(self):
        return self.xsi_lib.xsi_get_time(self.xsi_handle)

    def run(self, steps):
        return self.xsi_lib.xsi_run(self.xsi_handle, steps)

    def close(self):
        staus = self.get_status()
        self.xsi_lib.xsi_close(self.xsi_handle)
        return staus

    def get_port_number(self, name):
        return self.xsi_lib.xsi_get_port_number(self.xsi_handle, ctypes.create_string_buffer(name.encode("utf-8")))

    def get_error_info(self):
        return self.xsi_lib.xsi_close(self.xsi_handle)

    def get_status(self):
        return self.xsi_lib.xsi_get_status(self.xsi_handle)
