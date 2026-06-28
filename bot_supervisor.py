# --- START OF FILE bot_supervisor.py ---

import subprocess
import time
import sys
import gc
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

SCRIPT_TO_SUPERVISE = 'bot_manager.py'
PYTHON_EXECUTABLE = sys.executable or "python3"

BANNER = f"""
{Fore.CYAN}███████╗██╗   ██╗ ██████╗██╗  ██╗ ██████╗ 
██╔════╝╚██╗ ██╔╝██╔════╝██║  ██║██╔═══██╗
███████╗ ╚████╔╝ ██║     ███████║██║   ██║
╚════██║  ╚██╔╝  ██║     ██╔══██║██║   ██║
███████║   ██║   ╚██████╗██║  ██║╚██████╔╝
╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝ ╚═════╝ {Style.RESET_ALL}
       {Fore.YELLOW}>> ADVANCED OB52 BOT MANAGER <<{Style.RESET_ALL}
"""

LOG_COLORS = {
    "[SUCCESS]": Fore.GREEN + Style.BRIGHT,
    "[LOGIN]": Fore.GREEN,
    "[ONLINE]": Fore.GREEN,
    "[FAIL]": Fore.RED + Style.BRIGHT,
    "[ERROR]": Fore.RED,
    "[CRITICAL]": Fore.RED + Style.BRIGHT,
    "[CRASH]": Fore.RED + Style.BRIGHT,
    "[STOPPED]": Fore.YELLOW,
    "[LAUNCH]": Fore.CYAN,
    "[MANAGER]": Fore.MAGENTA,
    "[SYSTEM]": Fore.MAGENTA + Style.BRIGHT,
    "[WEB]": Fore.BLUE + Style.BRIGHT,
    "[LAW]": Fore.YELLOW
}

IGNORE_MESSAGES = ["Joined Guild Chat", "Refreshing connection"]

def print_styled_log(line):
    line = line.strip()
    color_prefix = Fore.WHITE
    for keyword, color in LOG_COLORS.items():
        if keyword in line:
            color_prefix = color
            break
    print(f"{color_prefix}{line}{Style.RESET_ALL}")

def supervise():
    print("\033[H\033[J", end="")
    print(BANNER)
    timestamp = f"[{datetime.now().strftime('%H:%M:%S')}]"
    print(f"{Fore.WHITE}{timestamp} {Fore.GREEN}[SYSTEM] Supervisor Active. Waiting for logs...{Style.RESET_ALL}\n")
    
    while True:
        try:
            gc.collect()
            cmd = [PYTHON_EXECUTABLE, '-u', SCRIPT_TO_SUPERVISE]
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                text=True, bufsize=1, encoding='utf-8', errors='replace'
            )
            
            start_ts = f"[{datetime.now().strftime('%H:%M:%S')}]"
            print(f"{Fore.WHITE}{start_ts} {Fore.MAGENTA}[SUPERVISOR] Manager Process Started (PID: {process.pid}){Style.RESET_ALL}")

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None: break
                
                if line:
                    if any(ignored in line for ignored in IGNORE_MESSAGES): continue
                    print_styled_log(line)

            # Check if process terminated by itself (crash)
            if process.poll() is not None: 
                crash_ts = f"[{datetime.now().strftime('%H:%M:%S')}]"
                print(f"{Fore.WHITE}{crash_ts} {Fore.YELLOW}[SUPERVISOR] Manager Stopped or Crashed! Initializing fresh startup in 2s...{Style.RESET_ALL}")
                time.sleep(2) 

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}[SUPERVISOR] Shutting down completely...{Style.RESET_ALL}")
            if 'process' in locals() and process.poll() is None:
                process.terminate()
            break
        except Exception as e:
            err_ts = f"[{datetime.now().strftime('%H:%M:%S')}]"
            print(f"{Fore.WHITE}{err_ts} {Fore.RED}[SUPERVISOR ERROR] {e}{Style.RESET_ALL}")
            time.sleep(5)

if __name__ == "__main__":
    supervise()

# --- END OF FILE bot_supervisor.py ---