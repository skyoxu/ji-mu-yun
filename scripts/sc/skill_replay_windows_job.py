"""Owned Windows process lifetime via nested Job Objects (Accepted ADR-0058).

The child starts suspended and joins its non-inheritable, kill-on-close job
before any candidate code can create descendants. No breakaway is permitted.
Only the owned PID's initial thread is resumed. A dead leader does not remove
its descendants from the job, unlike PID-based taskkill traversal.
"""
from __future__ import annotations

import ctypes
import time


# Explicit Win32 widths also make layout checks meaningful on other platforms.
DWORD, LONG, HANDLE = ctypes.c_uint32, ctypes.c_int32, ctypes.c_void_p
SIZE_T, ULONGLONG = ctypes.c_size_t, ctypes.c_uint64


class BasicLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", DWORD),
                ("MinimumWorkingSetSize", SIZE_T), ("MaximumWorkingSetSize", SIZE_T),
                ("ActiveProcessLimit", DWORD), ("Affinity", SIZE_T),
                ("PriorityClass", DWORD), ("SchedulingClass", DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ULONGLONG) for name in
                ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                 "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", SIZE_T), ("JobMemoryLimit", SIZE_T),
                ("PeakProcessMemoryUsed", SIZE_T), ("PeakJobMemoryUsed", SIZE_T)]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
                ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
    _fields_ += [(name, DWORD) for name in
                 ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]


class ThreadEntry(ctypes.Structure):
    _fields_ = [("dwSize", DWORD), ("cntUsage", DWORD), ("th32ThreadID", DWORD),
                ("th32OwnerProcessID", DWORD), ("tpBasePri", LONG),
                ("tpDeltaPri", LONG), ("dwFlags", DWORD)]


def kernel_api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([HANDLE, ctypes.c_wchar_p], HANDLE),
        "SetInformationJobObject": ([HANDLE, ctypes.c_int, HANDLE, DWORD], ctypes.c_int),
        "AssignProcessToJobObject": ([HANDLE, HANDLE], ctypes.c_int),
        "QueryInformationJobObject": ([HANDLE, ctypes.c_int, HANDLE, DWORD, HANDLE], ctypes.c_int),
        "TerminateJobObject": ([HANDLE, ctypes.c_uint], ctypes.c_int),
        "CreateToolhelp32Snapshot": ([DWORD, DWORD], HANDLE),
        "Thread32First": ([HANDLE, ctypes.POINTER(ThreadEntry)], ctypes.c_int),
        "Thread32Next": ([HANDLE, ctypes.POINTER(ThreadEntry)], ctypes.c_int),
        "OpenThread": ([DWORD, ctypes.c_int, DWORD], HANDLE),
        "ResumeThread": ([HANDLE], DWORD),
        "CloseHandle": ([HANDLE], ctypes.c_int),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return api


class WindowsJob:
    def __init__(self, api=None):
        self.api = api if api is not None else kernel_api()
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def assign_and_resume(self, process):
        # Popen retains the exact CreateProcess handle; reopening by a PID
        # would lose identity if another actor terminated this suspended child.
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = self.api.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD only
        if snapshot == HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            found = self.api.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.th32OwnerProcessID == process.pid:
                    thread = self.api.OpenThread(0x2, False, entry.th32ThreadID)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.api.ResumeThread(thread) != 1:
                            raise OSError("owned child initial thread did not resume from its single suspension")
                    finally:
                        self.api.CloseHandle(thread)
                    return
                entry.dwSize = ctypes.sizeof(entry)
                found = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            raise OSError("owned child initial thread was absent")
        finally:
            self.api.CloseHandle(snapshot)

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + 5
        while True:
            state = Accounting()
            if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(state), ctypes.sizeof(state), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if state.ActiveProcesses == 0:
                return
            if time.monotonic() >= deadline:
                raise OSError("owned job descendants did not exit within the cleanup budget")
            time.sleep(0.01)

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.api.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
