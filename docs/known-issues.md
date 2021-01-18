
- asan jobs requires privileged access.

  More details:  drone jobs run in docker containers. Asan needs ptrace, which requires privilege escalation. Add "privileged: True" to the .drone.star file, if it's not already there. Also, contact a drone administrator to escalate privileges on your repo.

- lcov errors.

  lcov should be upgraded to 1.14.
