Service Ghost
================

This is the source code for the "ghost" service from [FAUST CTF 2022](https://2022.faustctf.net).

**As it was written for a CTF service, the code is deliberately insecure and contains exploitable bugs. It
is provided for educational purposes only, do not even think about (re-) using it for anything productive!**

The code is released under the ISC License, see LICENSE.txt for details.

----

This service is similar to a malware contacting a C&C server for tasks to execute.

It's main idea is to be hidden quite well in the system.

The main code executed on the teams' machines is in `faust/service/code.py`. The 'exploit' is in `faust/exploiter/server.py`.

## Running
Instructions to test this locally. [Info how this is deployed in the contest]
- Start `python3 checker/perma_server.py` [this is done on a seperate machine that is within the teams' network]
- Start `python3 checker/ghost_checker.py 127.0.0.1 42 <tick>` [normal checker script invoked for each tick by the gameserver]
- Run `python3 faust/service/code.py` [this is repeatedly run on the teams' machines]

**Notes:**
- You have to start the `code.py` within the grace period after starting the checker. It can be configured in `perma_server.py` with the variable `WAIT_TIME_IN_TICK`. In the contest, this will probably be 90 (seconds).

Read README.SPOILER.md for further information.
