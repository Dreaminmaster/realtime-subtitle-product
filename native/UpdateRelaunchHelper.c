#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

// Sparkle can replace an EdDSA-authenticated, ad-hoc-signed bundle even when
// the Python GUI process is not recognized as the bundle executable to
// relaunch. This tiny helper waits for the old process to leave, then asks
// LaunchServices to open the already-installed application. It never downloads
// or installs anything and therefore remains part of the single Sparkle flow.
int main(int argc, char **argv) {
    if (argc != 3) return 64;

    char *end = NULL;
    long raw_pid = strtol(argv[1], &end, 10);
    if (end == argv[1] || *end != '\0' || raw_pid <= 1) return 65;
    pid_t old_pid = (pid_t)raw_pid;

    const struct timespec interval = {.tv_sec = 0, .tv_nsec = 200000000L};
    for (int attempt = 0; attempt < 100; ++attempt) {
        if (kill(old_pid, 0) != 0 && errno == ESRCH) break;
        nanosleep(&interval, NULL);
    }

    execl("/usr/bin/open", "open", "-n", argv[2], (char *)NULL);
    perror("Realtime Subtitle update relaunch failed");
    return 66;
}
