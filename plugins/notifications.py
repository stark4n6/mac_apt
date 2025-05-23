'''
   Copyright (c) 2017 Yogesh Khatri 

   This file is part of mac_apt (macOS Artifact Parsing Tool).
   Usage or distribution of this software/code is subject to the 
   terms of the MIT License.
   
'''

import logging
import os
import sqlite3
import uuid
from io import BytesIO

from plugins.helpers.common import *
from plugins.helpers.macinfo import *
from plugins.helpers.writer import *

__Plugin_Name = "NOTIFICATIONS" # Cannot have spaces, and must be all caps!
__Plugin_Friendly_Name = "Notifications"
__Plugin_Version = "1.1"
__Plugin_Description = "Reads notification databases"
__Plugin_Author = "Yogesh Khatri"
__Plugin_Author_Email = "yogesh@swiftforensics.com"

__Plugin_Modes = "MACOS,ARTIFACTONLY"
__Plugin_ArtifactOnly_Usage = '''This module parses the notification database for a user. 

For OSX Mavericks (and earlier), this is found at:
/Users/<profile>/Library/Application Support/NotificationCenter/<UUID>.db

For Yosemite, ElCapitan & Sierra, this is at: 
/private/var/folders/<xx>/<yyyyyyy>/0/com.apple.notificationcenter/db/db

For High Sierra, this is at:
/private/var/folders/<xx>/<yyyyyyy>/0/com.apple.notificationcenter/db2/db

 where the path <xx>/<yyyyyyy> represents the DARWIN_USER_DIR for a user

For Sequoia, this is at:
/Users/<profile>/Library/Group Containers/group.com.apple.usernoted/db2/db
'''
log = logging.getLogger('MAIN.' + __Plugin_Name) # Do not rename or remove this ! This is the logger object

#---- Do not change the variable names in above section ----#

notifications = []
data_info = [('User', DataType.TEXT),('Date', DataType.DATE),('Shown', DataType.INTEGER), \
            ('Bundle', DataType.TEXT),('AppPath', DataType.TEXT),('UUID', DataType.TEXT), \
            ('Title', DataType.TEXT),('SubTitle', DataType.TEXT),('Message', DataType.TEXT), \
            ('Identifier', DataType.TEXT),('Source', DataType.TEXT)]

def RemoveTabsNewLines(obj):
    if isinstance(obj, str):
        return obj.replace("\t", " ").replace("\r", " ").replace("\n", "")
    elif isinstance(obj, list): # On 10.15, sometimes its a list
        if len(obj) > 0:
            item = str(obj[0])
            return item.replace("\t", " ").replace("\r", " ").replace("\n", "")
    else:
        log.error('Unknown type found : ' + str(type(obj)))

def ProcessNotificationDb(inputPath, output_params, screentime_strings_dict=None):
    log.info ("Processing file " + inputPath)
    try:
        conn = CommonFunctions.open_sqlite_db_readonly(inputPath)
        log.debug ("Opened database successfully")
        ParseDb(conn, inputPath, '', output_params.timezone, screentime_strings_dict)
        conn.close()
    except sqlite3.Error as ex:
        log.error ("Failed to open database, is it a valid Notification DB? \nError details: " + str(ex.args))

def ProcessNotificationDb_Wrapper(inputPath, mac_info, user, screentime_strings_dict=None):
    log.info ("Processing notifications for user '{}' from file {}".format(user, inputPath))
    try:
        sqlite = SqliteWrapper(mac_info)
        conn = sqlite.connect(inputPath)
        if conn:
            log.debug ("Opened database successfully")
            ParseDb(conn, inputPath, user, mac_info.output_params.timezone, screentime_strings_dict)
            conn.close()
    except sqlite3.Error as ex:
        log.error ("Failed to open database, is it a valid Notification DB? Error details: " + str(ex)) 

def GetText(string_or_binary):
    '''Converts binary or text string into text string. UUID in Sierra is now binary blob instead of hex text.'''
    uuid_text = ''
    try:
        if isinstance(string_or_binary, bytes):
            uuid_text = str(uuid.UUID(bytes=string_or_binary)).upper()
        else:
            uuid_text = string_or_binary.upper()
    except ValueError as ex:
        log.error('Error trying to convert binary value to hex text. Details: ' + str(ex))
    return uuid_text

def GetDbVersion(conn):
    try:
        cursor = conn.execute("SELECT value from dbinfo WHERE key LIKE 'compatibleVersion'")
        for row in cursor:
            log.debug('db compatibleversion = {}'.format(row[0]))
            return int(row[0])
    except sqlite3.Error:
        log.exception("Exception trying to determine db version")
    return 15 #old version

def FetchScreenTimeItem(dictionary, item_name, screentime_strings_dict):
    ret = ''
    item = dictionary.get(item_name, '')
    if item and isinstance(item, list):
        if len(item) == 3:
            data = item[2]
            ret = screentime_strings_dict.get(item[0], '')
            num_variables = ret.count('%@')
            if num_variables:
                if ret.find('%@') >= 0 and num_variables == len(data):
                    for x in range(num_variables):
                        ret = ret.replace('%@', '{}', 1)
                        ret = ret.format(data[x])
                else:
                    log.error(f'Mismatch in number of variables and format string, format_string={ret}, data={str(data)}')
        else:
            log.error(f'List length was not 3, len={len(item)}, item_name={item_name}, item={str(item)}')
    else:
        ret = item
    return ret

def ProcessScreenTimeNotifications(req, screentime_strings_dict):
    title = FetchScreenTimeItem(req, 'titl', screentime_strings_dict)
    subtitle = FetchScreenTimeItem(req ,'subt', screentime_strings_dict)
    message = FetchScreenTimeItem(req, 'body', screentime_strings_dict)
    return title, subtitle, message

def Parse_ver_17_Db(conn, inputPath, user, timezone, screentime_strings_dict):
    '''Parse High Sierra's notification db'''
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT (SELECT identifier from app where app.app_id=record.app_id) as app, "\
                                "uuid, data, presented, delivered_date FROM record")
        try:
            for row in cursor:
                title    = ''
                subtitle = ''
                message  = ''
                success, plist, error = CommonFunctions.ReadPlist(BytesIO(row['data']))
                if success:
                    try:
                        req = plist['req']
                        app = plist.get('app', '')
                        if app == 'com.apple.ScreenTimeNotifications' and screentime_strings_dict:
                            title, subtitle, message = ProcessScreenTimeNotifications(req, screentime_strings_dict)
                        else:
                            title = RemoveTabsNewLines(req.get('titl', ''))
                            subtitle = RemoveTabsNewLines(req.get('subt', ''))
                            message = RemoveTabsNewLines(req.get('body', ''))
                            identifier = req.get('iden', '')
                    except (KeyError, AttributeError) as ex: log.debug('Error reading field req - ' + str(ex))
                    try:
                        log.debug('Unknown field orig = {}'.format(plist['orig']))
                    except (KeyError, ValueError): pass
                else:
                    log.error("Invalid plist in table." + error)

                notifications.append([user, CommonFunctions.ReadMacAbsoluteTime(row['delivered_date']) , 
                                        row['presented'], row['app'], '', GetText(row['uuid']), 
                                        title, subtitle, message, identifier, inputPath])       
        except sqlite3.Error as ex:
            log.error ("Db cursor error while reading file " + inputPath)
            log.exception("Exception Details")
    except sqlite3.Error as ex:
        log.error ("Sqlite error - \nError details: \n" + str(ex))

def ParseDb(conn, inputPath, user, timezone, screentime_strings_dict):
    '''variable 'timezone' is not being currently used'''
    if GetDbVersion(conn) >= 17: # High Sierra
        Parse_ver_17_Db(conn, inputPath, user, timezone, screentime_strings_dict)
        return
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT date_presented as time_utc, actually_presented AS shown, "
                                "(SELECT bundleid from app_info WHERE app_info.app_id = presented_notifications.app_id)  AS bundle, "
                                "(SELECT last_known_path from app_loc WHERE app_loc.app_id = presented_notifications.app_id)  AS appPath, "
                                "(SELECT uuid from notifications WHERE notifications.note_id = presented_notifications.note_id) AS uuid, "
                                "(SELECT encoded_data from notifications WHERE notifications.note_id = presented_notifications.note_id) AS dataPlist "
                                "from presented_notifications ")
        try:
            for row in cursor:
                title    = ''
                subtitle = ''
                message  = ''
                success, plist, error = CommonFunctions.ReadPlist(BytesIO(row['dataPlist']))
                if success:
                    title_index = 2 # by default
                    subtitle_index = -1 # mostly absent!
                    text_index = 3 # by default
                    try:
                        title_index = int(plist['$objects'][1]['NSTitle'])
                    except KeyError: pass
                    try:
                        subtitle_index = int(plist['$objects'][1]['NSSubtitle'])
                    except KeyError: pass
                    try:
                        text_index = int(plist['$objects'][1]['NSInformativetext'])
                    except KeyError: pass
                    try:
                        title = RemoveTabsNewLines(plist['$objects'][title_index])
                    except KeyError: pass
                    try:
                        subtitle = RemoveTabsNewLines(plist['$objects'][subtitle_index]) if subtitle_index > -1 else ""
                    except KeyError: pass                        
                    try:
                        message = RemoveTabsNewLines(plist['$objects'][text_index])
                    except KeyError: pass
                else:
                    log.error("Invalid plist in table." + error)

                notifications.append([user, CommonFunctions.ReadMacAbsoluteTime(row['time_utc']) , 
                                    row['shown'], row['bundle'], row['appPath'], GetText(row['uuid']), 
                                    title, subtitle, message, '', inputPath])
        except sqlite3.Error as ex:
            log.error ("Db cursor error while reading file " + inputPath)
            log.exception("Exception Details")
    except sqlite3.Error as ex:
        log.error ("Sqlite error - \nError details: \n" + str(ex))

def WriteOutput(output_params):
    if len(notifications) == 0: 
        log.info("No notification data was retrieved!")
        return
    else:
        log.info("{} notifications found".format(len(notifications)))
    try:
        log.debug ("Trying to write out parsed notifications data")
        writer = DataWriter(output_params, "Notifications", data_info)
        try:
            writer.WriteRows(notifications)
        except Exception as ex:
            log.error ("Failed to write row data")
            log.exception ("Error details")
        finally:
            writer.FinishWrites()
    except Exception as ex:
        log.error ("Failed to initilize data writer")
        log.exception ("Error details")

def  GetScreenTimeStrings(mac_info):
    strings = {}
    old_paths = ('/System/Library/UserNotifications/Bundles/com.apple.ScreenTimeNotifications.bundle/Contents/Resources/en.lproj/Localizable.strings',
                '/System/Library/UserNotifications/Bundles/com.apple.ScreenTimeNotifications.bundle/Contents/Resources/en.lproj/InfoPlist.strings')
    new_paths = ('/System/Library/UserNotifications/Bundles/com.apple.ScreenTimeNotifications.bundle/Contents/Resources/InfoPlist.loctable',
                '/System/Library/UserNotifications/Bundles/com.apple.ScreenTimeNotifications.bundle/Contents/Resources/Localizable.loctable')
    
    for path in old_paths:
        if mac_info.IsValidFilePath(path):
            success, plist, error = mac_info.ReadPlist(path)
            if success:
                strings.update(plist)
            else:
                log.error(f"Failed to read plist {path}")
        else:
            log.debug('Did not find path - ' + path)

    for path in new_paths:
        if mac_info.IsValidFilePath(path):
            success, plist, error = mac_info.ReadPlist(path)
            if success:
                # Only seen en_GB and en_AU, but just en and en_US too
                for lang in ('en_GB', 'en', 'en_US', 'en_AU'):
                    if lang in plist:
                        strings.update(plist[lang])
                        break
            else:
                log.error(f"Failed to read plist {path}")
        else:
            log.debug('Did not find path - ' + path)

    return strings

def Plugin_Start(mac_info):
    version_dict = mac_info.GetVersionDictionary()
    processed_paths = []

    if (version_dict['major'] == 10 and version_dict['minor'] <= 9) or version_dict['major'] >= 15:  # older than yosemite, ie, mavericks or earlier, or newer than Sequoia
        if version_dict["major"] >= 15:
            notification_path = "{}/Library/Group Containers/group.com.apple.usernoted/db2/db"
            screentime_strings_dict = GetScreenTimeStrings(mac_info)
        else:
            notification_path = "{}/Library/Application Support/NotificationCenter"
        for user in mac_info.users:
            user_name = user.user_name
            if user.home_dir == '/private/var': continue # Optimization, nothing should be here!
            elif user.home_dir == '/private/var/root': user_name = 'root' # Some other users use the same root folder, we will list such all users as 'root', as there is no way to tell
            if user.home_dir in processed_paths: continue # Avoid processing same folder twice (some users have same folder! (Eg: root & daemon))
            processed_paths.append(user.home_dir)
            user_notification_path = notification_path.format(user.home_dir)
            if version_dict["major"] >= 15 and mac_info.IsValidFilePath(user_notification_path):
                ProcessNotificationDb_Wrapper(user_notification_path, mac_info, user_name, screentime_strings_dict)
                mac_info.ExportFile(user_notification_path, __Plugin_Name, user_name + "_")
            elif version_dict["major"] < 15 and mac_info.IsValidFolderPath(user_notification_path):
                files = mac_info.ListItemsInFolder(user_notification_path, EntryType.FILES)
                for db in files:
                    # Not sure if this is the only file here
                    if db['name'].endswith('.db') and db['size'] > 0 :
                        db_path = user_notification_path + '/' + db['name']
                        ProcessNotificationDb_Wrapper(db_path, mac_info, user_name)
                        mac_info.ExportFile(db_path, __Plugin_Name, user_name + '_')
                        break
            
    elif (version_dict['major'] == 10 and version_dict['minor'] >= 10) or version_dict['major'] >= 11: # Yosemite or higher
        screentime_strings_dict = None
        if (version_dict['major'] == 10 and version_dict['minor'] >= 15) or version_dict['major'] >= 11: #Catalina or higher
            screentime_strings_dict = GetScreenTimeStrings(mac_info)
        for user in mac_info.users:
            if not user.DARWIN_USER_DIR or not user.user_name: continue # TODO: revisit this later!
            else:
                darwin_user_folders = user.DARWIN_USER_DIR.split(',')
                for darwin_user_dir in darwin_user_folders:
                    db_path = darwin_user_dir + '/com.apple.notificationcenter/db/db'
                    if mac_info.IsValidFilePath(db_path):
                        mac_info.ExportFile(db_path, __Plugin_Name, user.user_name + '_')
                        ProcessNotificationDb_Wrapper(db_path, mac_info, user.user_name, screentime_strings_dict)
                    #For High Sierra db2 is present. If upgraded, both might be present
                    db_path = darwin_user_dir + '/com.apple.notificationcenter/db2/db'
                    if mac_info.IsValidFilePath(db_path):
                        mac_info.ExportFile(db_path, __Plugin_Name, user.user_name + '_')
                        ProcessNotificationDb_Wrapper(db_path, mac_info, user.user_name, screentime_strings_dict)
    WriteOutput(mac_info.output_params)

## Standalone Plugin call

def Plugin_Start_Standalone(input_files_list, output_params):
    log.info("Module Started as standalone")
    for input_path in input_files_list:
        if os.path.isfile(input_path):
            ProcessNotificationDb(input_path, output_params)
        else:
            log.error("Input path is not a file! Please provide the path to a notifications database file")
    WriteOutput(output_params)

## 
if __name__ == '__main__':
    print("This plugin is a part of a framework and does not run independently on its own!")

