#import <Cocoa/Cocoa.h>
#import <Sparkle/Sparkle.h>
#include <unistd.h>

// Minimal C boundary used by the PyQt process. The portable-Python executable
// is NSBundle.mainBundle, not RealtimeSubtitle.app, so bind Sparkle explicitly
// to the outer app bundle.
// Sparkle remains responsible for its standard UI, release notes, download,
// signature verification, installation and relaunch lifecycle.
static SPUUpdater *RTUpdater = nil;
static SPUStandardUserDriver *RTUserDriver = nil;
static NSBundle *RTHostBundle = nil;
static NSString *RTLastError = nil;
static NSString *RTStartingVersion = nil;
static NSString *RTExpectedVersion = nil;
static bool RTRelaunchRequested = false;

@interface RTUpdaterDelegate : NSObject <SPUUpdaterDelegate>
@end

@implementation RTUpdaterDelegate
- (void)updater:(SPUUpdater *)updater didFindValidUpdate:(SUAppcastItem *)item {
    RTExpectedVersion = [item.versionString copy];
    NSLog(@"[RealtimeSubtitle.Update] found valid update %@", RTExpectedVersion);
}

- (BOOL)updater:(SPUUpdater *)updater
        willInstallUpdateOnQuit:(SUAppcastItem *)item
        immediateInstallationBlock:(void (^)(void))immediateInstallHandler {
    // Automatic updates are the single normal path. Once Sparkle has fully
    // downloaded and authenticated an update, install and relaunch instead
    // of leaving an invisible "install on quit" task behind for days.
    NSLog(@"[RealtimeSubtitle.Update] verified %@; installing and relaunching", item.displayVersionString);
    dispatch_async(dispatch_get_main_queue(), immediateInstallHandler);
    return YES;
}
@end

static RTUpdaterDelegate *RTDelegate = nil;

static void RTOnMain(dispatch_block_t block) {
    if ([NSThread isMainThread]) {
        block();
    } else {
        dispatch_async(dispatch_get_main_queue(), block);
    }
}

bool RTSparkleStart(const char *bundlePath) {
    __block bool started = false;
    RTOnMain(^{
        if (RTUpdater != nil) {
            started = true;
            return;
        }
        NSString *path = bundlePath == NULL ? nil : [NSString stringWithUTF8String:bundlePath];
        RTHostBundle = path.length > 0 ? [NSBundle bundleWithPath:path] : nil;
        if (RTHostBundle == nil) {
            RTLastError = @"Realtime Subtitle application bundle was not found.";
            NSLog(@"[RealtimeSubtitle.Update] %@ path=%@", RTLastError, path);
            return;
        }
        RTUserDriver = [[SPUStandardUserDriver alloc] initWithHostBundle:RTHostBundle delegate:nil];
        RTDelegate = [[RTUpdaterDelegate alloc] init];
        RTUpdater = [[SPUUpdater alloc]
            initWithHostBundle:RTHostBundle
            applicationBundle:RTHostBundle
            userDriver:RTUserDriver
            delegate:RTDelegate];
        NSError *error = nil;
        started = [RTUpdater startUpdater:&error];
        if (!started) {
            RTLastError = error.localizedDescription ?: @"Sparkle could not start.";
            NSLog(@"[RealtimeSubtitle.Update] start failed: %@", error);
            RTUpdater = nil;
            RTUserDriver = nil;
            RTDelegate = nil;
            RTHostBundle = nil;
        } else {
            RTLastError = nil;
            RTStartingVersion = [[RTHostBundle objectForInfoDictionaryKey:@"CFBundleVersion"] copy];
            RTExpectedVersion = nil;
            RTRelaunchRequested = false;
            NSLog(@"[RealtimeSubtitle.Update] updater started for %@ (%@)",
                  RTHostBundle.bundlePath,
                  RTStartingVersion);
        }
    });
    return started;
}

void RTSparkleCheckForUpdates(void) {
    RTOnMain(^{
        [RTUpdater checkForUpdates];
    });
}

void RTSparkleCheckForUpdatesInBackground(void) {
    RTOnMain(^{
        [RTUpdater checkForUpdatesInBackground];
    });
}

bool RTSparkleCanCheckForUpdates(void) {
    return RTUpdater != nil && RTUpdater.canCheckForUpdates;
}

bool RTSparkleAutomaticallyChecksForUpdates(void) {
    return RTUpdater != nil && RTUpdater.automaticallyChecksForUpdates;
}

void RTSparkleSetAutomaticallyChecksForUpdates(bool enabled) {
    RTOnMain(^{
        RTUpdater.automaticallyChecksForUpdates = enabled;
    });
}

bool RTSparkleAutomaticallyDownloadsUpdates(void) {
    return RTUpdater != nil && RTUpdater.automaticallyDownloadsUpdates;
}

static NSString *RTInstalledBundleVersion(void) {
    if (RTHostBundle.bundlePath.length == 0) return nil;
    NSString *infoPath = [RTHostBundle.bundlePath stringByAppendingPathComponent:@"Contents/Info.plist"];
    NSDictionary *info = [NSDictionary dictionaryWithContentsOfFile:infoPath];
    id version = info[@"CFBundleVersion"];
    return [version isKindOfClass:NSString.class] ? version : nil;
}

bool RTSparkleInstalledUpdateReady(void) {
    if (RTRelaunchRequested || RTExpectedVersion.length == 0 || RTStartingVersion.length == 0) return false;
    NSString *installedVersion = RTInstalledBundleVersion();
    return installedVersion.length > 0 &&
           ![installedVersion isEqualToString:RTStartingVersion] &&
           [installedVersion isEqualToString:RTExpectedVersion];
}

bool RTSparklePrepareRelaunch(void) {
    if (!RTSparkleInstalledUpdateReady()) return false;
    NSString *helper = [RTHostBundle.bundlePath stringByAppendingPathComponent:
        @"Contents/Resources/bin/update-relaunch-helper"];
    if (![[NSFileManager defaultManager] isExecutableFileAtPath:helper]) {
        RTLastError = @"The update relaunch helper is missing.";
        NSLog(@"[RealtimeSubtitle.Update] %@ path=%@", RTLastError, helper);
        return false;
    }

    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:helper];
    task.arguments = @[[NSString stringWithFormat:@"%d", getpid()], RTHostBundle.bundlePath];
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        RTLastError = error.localizedDescription ?: @"The update relaunch helper could not start.";
        NSLog(@"[RealtimeSubtitle.Update] relaunch helper failed: %@", error);
        return false;
    }
    RTRelaunchRequested = true;
    NSLog(@"[RealtimeSubtitle.Update] installed %@; restarting application", RTExpectedVersion);
    return true;
}

void RTSparkleSetAutomaticallyDownloadsUpdates(bool enabled) {
    RTOnMain(^{
        RTUpdater.automaticallyDownloadsUpdates = enabled;
    });
}

const char *RTSparkleLastError(void) {
    return RTLastError.UTF8String;
}
