[app]

# (str) Title of your application
title = 看单词

# (str) Package name
package.name = vocabapp

# (str) Package domain (needed for android/ios packaging)
package.domain = org.claw

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,json,png,jpg,kv,atlas,ttf,otf

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = bin,.buildozer,.git,.github,tools,__pycache__

# (list) List of exclusions using pattern matching
#source.exclude_patterns = license,data/audio/*.wav,data/images/*.jpeg

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
#comma separated list of requirements to add to the application
requirements = python3,kivy

# (str) Custom source folders for requirements (Repos external to python-for-android)
#requirements.source.kivy = 

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (list) Supported orientations
# Valid options are: landscape, portrait, portrait-reverse or landscape-reverse
orientation = portrait

# (list) List of service to declare
#services = NAME:ENTRYPOINT_TO_PY,NAME2:ENTRYPOINT2_TO_PY

#
# OSX Specific
#

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (string) Presplash background color (for android toolchain)
#android.presplash_color = #FFFFFF

# (list) Permissions
android.permissions = INTERNET

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (str) Android NDK version to use
#android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) The Android archs to build for
# 只编 arm64-v8a：现代手机（2017 年后）全支持，构建时间减半
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (bool) 自动回答 Android SDK 许可协议（否则 sdkmanager 卡在许可提示，
#       导致 build-tools 装不上、报 "Aidl not found"）
android.accept_sdk_license = True

# (str) The format used to package the app for release mode (aab or apk or aar).
android.release_artifact = apk

# (str) The format used to package the app for debug mode (apk or aar).
android.debug_artifact = apk

# (list) Android additional libraries to copy into libs/armeabi
#android.add_libs_armeabi = libs/android/*.so

#
# Python for android (p4a) specific
#

# (str) python-for-android URL to use for checkout
#p4a.url =

# (str) python-for-android fork to use in case if p4a.url is not specified, defaults to upstream (if empty)
#p4a.fork = kivy

# (str) python-for-android branch to use, defaults to master
# 必须钉到发行版：master 分支的 python3 recipe 已是 3.14.x，
# 其自带 pip 在自升级时会出现文件混版（pip._internal.utils.logging 缺 capture_logging）导致构建失败。
# v2024.01.21 = Python 3.11.5 + NDK 25b，是验证最多的稳定组合。
p4a.branch = v2024.01.21

# (str) python-for-android git clone directory (if empty, it will be automatically cloned from github)
#p4a.local =

# (str) Filename to the hook for p4a
#p4a.hook =

# (str) Bootstrap to use for android builds
#p4a.bootstrap = sdl2

# (int) port number to specify an explicit --port= p4a argument (eg for bootstrap flask)
#p4a.port =

# Control passing the --use-setup-py vs --ignore-setup-py to p4a
# 本项目没有 setup.py，p4a 会自动跳过，无需额外参数

#
# iOS specific
#
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
build_dir = ./.buildozer

# (str) Path to build output (i.e. .apk, .aab, .ipa) storage
bin_dir = ./bin

# (str) Path to .env file to load for buildozer
# env_file = .env

# (str) Path to the Java compiler... (set JAVA_HOME)
#java_home =
