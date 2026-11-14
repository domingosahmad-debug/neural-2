import os
class ChildLifetime:
    """Windows kills this local subprocess tree if its Python owner crashes."""
    def __init__(self):
        self.handle=None
        if os.name!='nt':return
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('processes',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):_fields_=[(n,ctypes.c_uint64) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Limits(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];self.kernel.CreateJobObjectW.restype=w.HANDLE
        self.kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
        self.kernel.CloseHandle.argtypes=[w.HANDLE]
        self.handle=self.kernel.CreateJobObjectW(None,None)
        if not self.handle:raise OSError('Cannot create local tool lifetime guard')
        limits=Limits();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close();raise OSError('Cannot configure local tool lifetime guard')

    def attach(self, process):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle,int(process._handle)):
            import ctypes
            error=ctypes.get_last_error()
            # A short probe may finish between Popen and job assignment.
            # Its normal return-code check still applies; no live child is exempt.
            if process.poll() is not None:return
            raise OSError(error,'Cannot attach local tool to its lifetime guard')

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


