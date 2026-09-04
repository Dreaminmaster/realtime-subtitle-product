#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

// Mach-O launcher required for a correctly signed/notarized application
// bundle.  It replaces the former shell CFBundleExecutable while preserving
// the existing portable-Python bootstrap behavior.
int main(int argc, char **argv) {
    uint32_t size = 0;
    _NSGetExecutablePath(NULL, &size);
    char *executable = calloc(size + 1, 1);
    if (!executable || _NSGetExecutablePath(executable, &size) != 0) return 70;

    char resolved[PATH_MAX];
    if (!realpath(executable, resolved)) return 71;
    free(executable);

    char macos_copy[PATH_MAX];
    strlcpy(macos_copy, resolved, sizeof(macos_copy));
    char *macos_dir = dirname(macos_copy);

    char resources[PATH_MAX];
    snprintf(resources, sizeof(resources), "%s/../Resources", macos_dir);
    char python[PATH_MAX];
    char launcher[PATH_MAX];
    snprintf(python, sizeof(python), "%s/python/bin/python3", resources);
    snprintf(launcher, sizeof(launcher), "%s/launcher.py", resources);

    char python_home[PATH_MAX];
    snprintf(python_home, sizeof(python_home), "%s/python", resources);
    setenv("PYTHONHOME", python_home, 1);
    // A signed application bundle must remain immutable after first launch.
    // Python otherwise creates __pycache__ beside bundled source and stdlib
    // files, invalidating the outer code signature (including Developer ID).
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    if (chdir(resources) != 0) return 72;

    char **child_argv = calloc((size_t)argc + 2, sizeof(char *));
    if (!child_argv) return 73;
    child_argv[0] = python;
    child_argv[1] = launcher;
    for (int index = 1; index < argc; ++index) child_argv[index + 1] = argv[index];
    child_argv[argc + 1] = NULL;
    execv(python, child_argv);
    fprintf(stderr, "Realtime Subtitle launcher failed: %s\n", strerror(errno));
    return 74;
}
