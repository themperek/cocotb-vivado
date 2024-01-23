from cocotb_vivado import xsi

MODULE = 0
REG = 1


class XsiPortHandle(object):
    def __init__(self, mgr, name, port_id, size):
        self.name = name
        self.port_id = port_id

        self.size = size
        self.mgr = mgr

    def get_const(self):
        return False

    def get_type(self):
        return REG

    def get_name_string(self):
        return self.name

    def get_type_string(self):
        return "REG"

    def get_definition_name(self):
        return ""

    def get_definition_file(self):
        return ""

    def get_num_elems(self):
        return self.size

    def get_range(self):
        return (self.size - 1, 0)

    def set_signal_val_int(self, action, value):
        str_value = f"{value:0{self.size}b}"
        self.mgr.xsi.put_value(self.port_id, str_value)

    def set_signal_val_binstr(self, action, value):
        self.mgr.xsi.put_value(self.port_id, value)

    def get_signal_val_binstr(self):
        return self.mgr.xsi.get_value(self.port_id)


class XsimRootHandle(object):
    def __init__(self, mgr):
        self.mgr = mgr

    def get_const(self):
        return True

    def get_type(self):
        return MODULE

    def get_name_string(self):
        return "top"

    def get_type_string(self):
        return "MODULE"

    def get_definition_name(self):
        return ""

    def get_definition_file(self):
        return ""

    def iterate(self, nothing):
        for name in self.mgr.ports:
            yield self.mgr.ports[name]

    def get_handle_by_name(self, name):
        if name not in self.mgr.ports:
            raise Exception(f"Port {name} does not exit!")

        return self.mgr.ports[name]


class CbClosure(object):
    def __init__(self, time_off, cb, ud):
        self.time_off = time_off
        self.cb = cb
        self.ud = ud
        self.cb_id = 1

    def __call__(self):
        if self.cb is not None:
            self.cb(self.ud)

    def deregister(self):
        self.cb = None


class Mgr(object):
    _inst = None

    def __init__(self, xsim_design):
        self.xsim_design = xsim_design

        self.cb_d = {}
        self._stop_request = False

        self.xsi = xsi.XSI(self.xsim_design)

        self.ports = {}
        self.init_ports()

    def get_design_name(self):
        return self.xsim_design

    def init_ports(self):
        ports_num = self.xsi.ports_number()
        for port_id in range(ports_num):
            name = self.xsi.get_port_name(port_id)
            size = self.xsi.get_port_size(port_id)
            self.ports[name] = XsiPortHandle(self, name, port_id, size)

    def run(self):
        """Propagates events as long as callbacks are registered"""

        while not self._stop_request and (len(self.cb_d) > 0):
            next = list(self.cb_d)[0]
            time_to_run = next - self.xsi.get_time()
            self.xsi.run(time_to_run)

            for cb in self.cb_d[next]:
                cb()

            self.cb_d.pop(next)

        return self._stop_request

    def stop_simulator(self):
        self._stop_request = True
        error = self.xsi.close()
        print(f"End simulation with status {xsi.XSI.status[error]}")

    def get_sim_time(self):
        time = self.xsi.get_time()
        return ((time >> 32), time & 0xFFFFFFFF)

    def get_precision(self):
        return self.xsi.get_precision()

    def register_timed_callback(self, t, cb, ud):
        ret = CbClosure(t, cb, ud)

        time = self.xsi.get_time()
        time_to_fire = time + t

        if time_to_fire in self.cb_d:
            self.cb_d[time_to_fire].append(ret)
        else:
            self.cb_d[time_to_fire] = [ret]

        # use https://grantjenks.com/docs/sortedcontainers/ ?
        self.cb_d = dict(sorted(self.cb_d.items()))

        return ret

    def get_root_handle(self):
        return XsimRootHandle(self)

    @classmethod
    def inst(cls):
        if cls._inst is None:
            raise Exception("Simulation manager (Mgr) not initialized")
        return cls._inst

    @classmethod
    def init(cls, xsim_design):
        cls._inst = Mgr(xsim_design)
        return cls._inst

    # HACK / CHANGE !
    @classmethod
    def close(cls):
        cls._inst = None
