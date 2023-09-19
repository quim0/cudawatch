# Copyright (c) 2023 Quim Aguado
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import subprocess
import argparse
import time
import signal
import sys

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# nvidia-smi --help-query-gpu
parameters_to_check = [
    # Total memory reserved by the NVIDIA driver and firmware.
    "memory.reserved", # MiB
    # Total memory allocated by active contexts.
    "memory.used", # MiB
    # Total free memory.
    "memory.free", # MiB
    # Core GPU temperature. in degrees C.
    "temperature.gpu", # C
    # HBM memory temperature. in degrees C.
    "temperature.memory", # C
    # A flag that indicates whether power management is enabled. Either
    # "Supported" or "[Not Supported]". Requires Inforom PWR object version 3.0
    # or higher or Kepler device.
    "power.management",
    # The last measured power draw for the entire board, in watts. Only
    # available if power management is supported. This reading is accurate to
    # within +/- 5 watts.
    "power.draw", # W
    # Current frequency of SM (Streaming Multiprocessor) clock.
    "clocks.current.sm", # MHz
    # Current frequency of memory clock.
    "clocks.current.memory" # MHz
]

def safeint(x):
    try:
        return int(x)
    except:
        try:
            return float(x)
        except:
            return None
    return None

parameters_lambdas = [
    safeint, # "memory.reserved"
    safeint, # "memory.used"
    safeint, # "memory.free"
    safeint, # "temperature.gpu"
    safeint, # "temperature.memory"
    lambda x: True if x == 'Enabled' else False, # "power.management"
    safeint, # "power.draw"
    safeint, # "clocks.current.sm"
    safeint, # "clocks.current.memory"
]

def cudawatch():
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser()

    # Required positional argument
    parser.add_argument("-c", "--command", type=str, help="Command to execute", required=True)
    parser.add_argument("-s", "--sampling-interval", type=int, help="Sampling interval, in milliseconds", required=False, default=500)
    parser.add_argument("-d", "--delay", type=int, help="Delay (in seconds) before the sampling starts", required=False, default=0)
    args = parser.parse_args()

    sampling_interval = args.sampling_interval
    QUERY_CMD = "nvidia-smi --format=csv,noheader,nounits --query-gpu={} --loop-ms={}".format(
            ','.join(parameters_to_check), sampling_interval
            )

    print( "--------------MONITORING-----------------------")

    tbegin = time.time_ns()

    try:
        pgpu = subprocess.Popen(args.command.split())

        time.sleep(args.delay)
        p = subprocess.Popen(QUERY_CMD.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        pgpu.communicate()
    except KeyboardInterrupt:
        try:
            pgpu.terminate()
        except OSError:
            pass
        pgpu.communicate()

    tend = time.time_ns()

    # Kill the process running nvidia-smi when the main process is done
    p.send_signal(signal.SIGINT)
    (output, err) = p.communicate()

    print( "-----------------------------------------------")

    # Time in seconds
    tdiff = ((tend - tbegin) / 1000000000) - args.delay
    if tdiff < 1:
        print(f"{bcolors.FAIL}{bcolors.BOLD}ERROR{bcolors.ENDC}{bcolors.FAIL}: Sampling interval is 1s, executions <1s can not be profiled.{bcolors.ENDC}")
        quit()

    if tdiff < 5:
        print(f"{bcolors.WARNING}{bcolors.BOLD}WARNING{bcolors.ENDC}{bcolors.WARNING}: Sampling interval is 1s, executions <5s may led to innacurate results.{bcolors.ENDC}")

    if err:
        print(f"nvidia-smi returned some errors:\n\t{str(err)}")
        quit()
    elif output:
        max_mem = 0
        min_temp = 10000
        max_temp = 0
        min_power = 10000
        max_power = 0
        sum_watts = 0
        csv_lines = [x.split(',') for x in output.decode('ascii').split('\n')]
        num_lines = 0
        for line in csv_lines:
            if len(line) == 0 or (len(line) == 1 and len(line[0]) == 0):
                # Empty line
                continue
            if len(line) != len(parameters_lambdas):
                print(len(line), len(parameters_lambdas))
                print(line)
                raise ValueError('Invalid number of columns returned by nvidia-smi')
            (mem_driver, mem_used, mem_free, temp_core, temp_mem,
            power_management, power, clock_sm, clock_mem) = [parameters_lambdas[idx](x) for (idx, x) in enumerate(line)]

            max_mem = max(max_mem, mem_used)
            max_temp = max(max_temp, temp_core)
            min_temp = min(min_temp, temp_core)
            max_power = max(max_power, power)
            min_power = min(min_power, power)
            sum_watts += power
            num_lines += 1
    else:
        print("nvidia-smi returned no data.")
        quit()

    print(f"{bcolors.BOLD}SUMMARY{bcolors.ENDC}")
    print(f"\t{bcolors.BOLD}{bcolors.UNDERLINE}Memory{bcolors.ENDC}")
    print(f"\tMax memory used:          {max_mem} MiB ({max_mem/1024:.2f} GiB)")
    print(f"\t{bcolors.BOLD}{bcolors.UNDERLINE}Temperature{bcolors.ENDC}")
    print(f"\tMax core GPU temperature: {max_temp} ºC")
    print(f"\tMin core GPU temperature: {min_temp} ºC")
    print(f"\t{bcolors.BOLD}{bcolors.UNDERLINE}Power{bcolors.ENDC}")
    print(f"\tMax power:  {max_power:.2f} W")
    print(f"\tMin power:  {min_power:.2f} W")
    print(f"\tAvg power:  {sum_watts/num_lines:.2f} W")
    #print(f"\tUsed power: {sum_watts/3600:.2f} Wh")

if __name__ == '__main__':
    cudawatch()
