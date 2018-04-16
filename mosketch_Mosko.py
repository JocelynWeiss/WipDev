# FIXME: some 6 DoFs joints may have initial rotation too. So take this into account

# coding: utf8
from __future__ import unicode_literals
"""
Mosketch for maya.
See https://github.com/MokaStudio/MosketchForMaya for more informations.
"""

import os, sys, locale

import json

import pymel.core as pmc
import maya.OpenMayaUI as OpenMayaUI
import maya.mel as mel

# Support for Qt4 and Qt5 depending on Maya version
from Qt import QtCore
from Qt import QtGui
from Qt import QtWidgets
from Qt import __version__
from Qt import QtNetwork

from Qt import __binding__
if __binding__ in ('PySide2', 'PyQt5'):
    from shiboken2 import wrapInstance
elif __binding__ in ('PySide', 'PyQt4'):
    from shiboken import wrapInstance
else:
    _print_error("cannot find Qt bindings")

# Global variables
MAIN_WINDOW = None
STATUS_TEXT = None
CONNECTION = None
IP = "127.0.0.1"
MOSKETCH_PORT = 16094

# Keys for Json packets
JSON_KEY_TYPE = "Type"
JSON_KEY_NAME = "Name"
JSON_KEY_ANATOMIC = "Anatom"
JSON_KEY_ROTATION = "LR"
JSON_KEY_TRANSLATION = "LT"
JSON_KEY_JOINTS = "Joints"
JSON_KEY_MODE = "Mode"

# MAYA JOINTS BUFFERS
JOINTS_BUFFER = {}
JOINTS_INIT_ORIENT_INV_BUFFER = {}
JOINTS_ROTATE_AXIS_INV_BUFFER = {}
INTER_JOINTS_BUFFER = {}
JOINTS_UUIDS = {}

ROOTS_SYSTEM = {}

# Verbose level (1 for critical informations, 3 to output all packets)
VERBOSE = 1

# RIG Prefix
PREFIX_FKX = "FKX"
PREFIX_FK = "FK"

################################################################################
##########          MAIN FUNCTIONS
################################################################################
def install():
    """
    Call this function to install Mosketch for Maya
        mosketch_for_maya.install()
    """
    shelf_name = "MosketchForMaya"

    # First get maya "official" shelves layout
    top_level_shelf_layout = mel.eval("global string $gShelfTopLevel; $temp = $gShelfTopLevel;")
    # Get all shelves
    shelf_layout = pmc.shelfLayout(shelf_name, parent=top_level_shelf_layout)
    start_icon_name = os.path.dirname(os.path.abspath(__file__)) + "/start.png"
    stop_icon_name = os.path.dirname(os.path.abspath(__file__)) + "/stop.png"
    pmc.shelfButton(label='Start',
                    parent=shelf_layout, 
                    image1=start_icon_name, 
                    command='import mosketch_for_maya;mosketch_for_maya.start()')
    pmc.shelfButton(label='Stop',
                    parent=shelf_layout,
                    image1=stop_icon_name,
                    command='mosketch_for_maya.stop()')

def start():
    """
    Call this function from Maya (in a shelf button or in script editor for example):
        import mosketch_for_maya
        mosketch_for_maya.start()
    """
    _create_gui()

def stop():
    """
    Call this function from Maya (in a shelf button or in script editor for example):
        mosketch_for_maya.stop()
    """
    # Close connection if any is still opened
    if CONNECTION is not None:
        _close_connection()

    _destroy_gui()

################################################################################
##########          GUI
################################################################################
def _create_gui():
    global MAIN_WINDOW
    global STATUS_TEXT

    maya_window = _get_maya_main_window()
    MAIN_WINDOW = QtWidgets.QMainWindow(maya_window)
    MAIN_WINDOW.setWindowTitle("Mosko rigged 0.54")

    content = QtWidgets.QWidget(MAIN_WINDOW)
    main_layout = QtWidgets.QVBoxLayout(content)

    help_text = QtWidgets.QLabel(content)
    help_text.setWordWrap(True)

    help_text.setText("""<br>
    <b>Please read <a href='https://github.com/MokaStudio/MosketchForMaya' style=\"color: #F16521;\"> documentation</a> first.</b>
    <br>""")
    help_text.setOpenExternalLinks(True)

    ip_label = QtWidgets.QLabel("IP", content)
    ip_lineedit = QtWidgets.QLineEdit(content)
    ip_lineedit.setText(IP)
    ip_lineedit.textChanged.connect(_ip_text_changed)
    ip_layout = QtWidgets.QHBoxLayout()
    ip_layout.addWidget(ip_label)
    ip_layout.addWidget(ip_lineedit)

    buttons_layout = QtWidgets.QHBoxLayout()
    connect_button = QtWidgets.QToolButton(content)
    connect_button.setText("CONNECT")
    connect_button.clicked.connect(_open_connection)
    buttons_layout.addWidget(connect_button)
    disconnect_button = QtWidgets.QToolButton(content)
    disconnect_button.setText("DISCONNECT")
    disconnect_button.clicked.connect(_close_connection)
    buttons_layout.addWidget(disconnect_button)
    update_mosketch_button = QtWidgets.QToolButton(content)
    update_mosketch_button.setText("UPDATE MOSKETCH")
    update_mosketch_button.setCheckable(False)
    update_mosketch_button.clicked.connect(_update_mosketch)
    buttons_layout.addWidget(update_mosketch_button)

    spacer = QtWidgets.QSpacerItem(10, 20)

    STATUS_TEXT = QtWidgets.QLabel(content)
    STATUS_TEXT.setWordWrap(True)
    STATUS_TEXT.setText("Not connected yet")

    content.setLayout(main_layout)
    main_layout.addWidget(help_text)
    main_layout.addLayout(ip_layout)
    main_layout.addLayout(buttons_layout)
    MAIN_WINDOW.setCentralWidget(content)
    main_layout.addSpacerItem(spacer)
    main_layout.addWidget(STATUS_TEXT)

    _print_verbose(sys.version, 1)
    _print_verbose(sys.getdefaultencoding(), 2)
    _print_verbose(sys.getfilesystemencoding(), 2)
    _print_verbose(sys.prefix, 2)
    _print_verbose(locale.getdefaultlocale(), 2)
    
    MAIN_WINDOW.show()

def _destroy_gui():
    MAIN_WINDOW.close()

def _get_maya_main_window():
    OpenMayaUI.MQtUtil.mainWindow()
    ptr = OpenMayaUI.MQtUtil.mainWindow()
    if ptr is None:
        raise RuntimeError('No Maya window found.')

    window = wrapInstance(long(ptr), QtWidgets.QMainWindow)
    assert isinstance(window, QtWidgets.QMainWindow)
    return window

def _ip_text_changed(text):
    global IP
    IP = text

# Helpers
def _print_error(error):
    global STATUS_TEXT

    error_msg = "ERROR: " + error
    print error_msg
    STATUS_TEXT.setText(error_msg)

def _print_success(success):
    global STATUS_TEXT

    success_msg = "SUCCESS: " + success
    print success_msg
    STATUS_TEXT.setText(success_msg)

def _print_encoding(string):
    if isinstance(string, str):
        print "ordinary string"
    elif isinstance(string, unicode):
        print "unicode string"
    else:
        print "not a recognized string encoding"

def _print_verbose(msg, verbose_level):
    global VERBOSE
    if verbose_level <= VERBOSE:
        print(msg)

################################################################################
##########          CONNECTION
################################################################################
def _get_connection_name():
    global IP
    global MOSKETCH_PORT

    return IP + ":" + str(MOSKETCH_PORT)

def _open_connection():
    global CONNECTION
    global IP
    global MOSKETCH_PORT

    if CONNECTION is not None:
        _print_error("connection is already opened.")
        return

    # Try to connect
    CONNECTION = QtNetwork.QTcpSocket(MAIN_WINDOW)
    CONNECTION.readyRead.connect(_got_data)
    CONNECTION.error.connect(_got_error)
    CONNECTION.connected.connect(_connected)
    CONNECTION.disconnected.connect(_disconnected)

    print "Trying to connect to " + _get_connection_name()
    CONNECTION.connectToHost(IP, MOSKETCH_PORT)

def _close_connection():
    global CONNECTION
    global JOINTS_BUFFER
    global JOINTS_INIT_ORIENT_INV_BUFFER
    global JOINTS_ROTATE_AXIS_INV_BUFFER

    if CONNECTION is None:
        _print_error("connection is already closed.")
        return

    CONNECTION.close()
    CONNECTION = None
    JOINTS_BUFFER = {}
    JOINTS_INIT_ORIENT_INV_BUFFER = {}
    JOINTS_ROTATE_AXIS_INV_BUFFER = {}

def _connected():
    _print_success("connection opened on " + _get_connection_name())

def _disconnected():
    global CONNECTION

    _print_success("connection closed on " + _get_connection_name())

    if CONNECTION is not None:
        CONNECTION.close() # Just in case
        CONNECTION = None

def _got_error(socket_error):
    global CONNECTION

    try:
        err_msg = CONNECTION.errorString()
        _print_error(err_msg)
    except Exception, e:
        _print_error("connection is not opened yet.")

    if socket_error == QtNetwork.QTcpSocket.ConnectionRefusedError:
        CONNECTION = None

################################################################################
##########          SEND
################################################################################
def _update_mosketch():
    '''
    We send "full" local rotations and local translations.
    So we need to add rotate axis and joint orient.
    '''
    global JOINTS_BUFFER
    global JOINTS_INIT_ORIENT_INV_BUFFER
    global JOINTS_ROTATE_AXIS_INV_BUFFER

    global JSON_KEY_TYPE
    global JSON_KEY_NAME
    global ROOTS_SYSTEM
    global JSON_KEY_ROTATION
    global JSON_KEY_TRANSLATION

    # Useless to prepare the data if we have no connection
    if CONNECTION is None:
        _print_error("Mosketch is not connected!")
        return
    # For every joint, pack data, then send packet
    try:
        quat = pmc.datatypes.Quaternion()
        joints_buffer_values = JOINTS_BUFFER.values()
        joints_stream = {}
        joints_stream[JSON_KEY_TYPE] = "JointsStream"
        joints_stream['Joints'] = []
        for maya_joint in joints_buffer_values:
            joint_data = {} # Reinit it
            idxName = maya_joint.name()
            if idxName.startswith(PREFIX_FKX):
                idxName = idxName.replace(PREFIX_FKX, "", 1)
                #print maya_joint.name() + " - " + idxName
            elif idxName.startswith(PREFIX_FK):
                idxName = idxName.replace(PREFIX_FK, "", 1)
                #print maya_joint.name() + " - " + idxName
            elif idxName == "RootX_M":
                joint_data[JSON_KEY_NAME] = idxName # Fill the Json key for the name
                # For this controller we need to take an offset into account
                offset = ROOTS_SYSTEM["RootCenter_M"];
                oT = offset.getTranslation(space='transform')
                # The root controller has an pre transform
                offset = ROOTS_SYSTEM["FKOffsetRoot_M"];
                oJO = offset.getRotation(space='transform', quaternion=True)
                RO = JOINTS_ROTATE_AXIS_INV_BUFFER[idxName].inverse()
                JO = JOINTS_INIT_ORIENT_INV_BUFFER[idxName].inverse()
                quat = maya_joint.getRotation(space='transform', quaternion=True)
                quat = oJO * RO * quat * JO * oJO.inverse()
                joint_data[JSON_KEY_ROTATION] = [quat[0], quat[1], quat[2], quat[3]]

                translation = maya_joint.getTranslation(space='transform')
                translation += oT
                translation *= 0.01 # Mosketch uses meters. Maya uses centimeters
                joint_data[JSON_KEY_TRANSLATION] = [translation[0], translation[1], translation[2]]
                joints_stream['Joints'].append(joint_data)
                continue
            else:
                continue

            joint_data[JSON_KEY_NAME] = idxName # Fill the Json key for the name

            # W = [S] * [RO] * [R] * [JO] * [IS] * [T]
            RO = JOINTS_ROTATE_AXIS_INV_BUFFER[idxName].inverse()
            JO = JOINTS_INIT_ORIENT_INV_BUFFER[idxName].inverse()
            quat = maya_joint.getRotation(space='transform', quaternion=True)
            quat = RO * quat * JO
            joint_data[JSON_KEY_ROTATION] = [quat[0], quat[1], quat[2], quat[3]]
            #print maya_joint.name() + " " + str(RO[0]) + " " + str(RO[1]) + " " + str(RO[2]) + " " + str(RO[3]) + "; " + str(JO[0]) + " " + str(JO[1]) + " " + str(JO[2]) + " " + str(JO[3])

            translation = maya_joint.getTranslation(space='transform')
            translation *= 0.01 # Mosketch uses meters. Maya uses centimeters
            joint_data[JSON_KEY_TRANSLATION] = [translation[0], translation[1], translation[2]]
            joints_stream['Joints'].append(joint_data)
            #print "Appending " + str(joint_data['Name'])
        json_data = json.dumps(joints_stream)
        CONNECTION.write(json_data)
    except Exception, e:
        _print_error("cannot send joint value (" + str(e) + ")")


################################################################################
##########          Ack hierarchy
################################################################################
def _send_ack_hierarchy_initialized():
    '''
    We send an acknowlegment to let Mosketch know that from now, it can send the JointsStream.
    '''
    # Useless to prepare the data if we have no connection
    if CONNECTION is None:
        _print_error("Mosketch is not connected!")
        return
    try:
        ack_packet = {}
        ack_packet['Type'] = "AckHierarchyInitialized"
        json_data = json.dumps(ack_packet)
        CONNECTION.write(json_data)
        CONNECTION.flush() # You need to flush so it's not concatenated with another packet.
        _print_verbose("AckHierarchyInitialized sent", 1)

    except Exception, e:
        _print_error("cannot send AckHierarchyInitialized (" + str(e) + ")")


################################################################################
##########          Ack joints stream
################################################################################
def _send_ack_jointstream_received():
    '''
    We send an acknowlegment to let Mosketch know that we received JointsStream.
    '''
    # Useless to prepare the data if we have no connection
    if CONNECTION is None:
        _print_error("Mosketch is not connected!")
        return
    try:
        ack_packet = {}
        ack_packet['Type'] = "JointsStreamAck"
        json_data = json.dumps(ack_packet)
        CONNECTION.write(json_data)
        #_print_verbose("JointsStreamAck sent", 1)

    except Exception, e:
        _print_error("cannot send JointsStreamAck (" + str(e) + ")")


################################################################################
##########          RECEIVE
################################################################################
def _got_data():
    """
    We may receive different types of data:
        - Type == "Hierarchy" => Initialize skeleton
        - Type == "JointsStream" => Copy paste received values on Maya's joints
    """
    try:
        raw_data = CONNECTION.readAll()
        
        if raw_data.isEmpty() is True:
            _print_verbose("Raw data from CONNECTION is empty", 1)
            return

        json_data = str(raw_data)
        _process_data(json_data)

    except Exception as e:
        _print_error("cannot read received data (" + type(e).__name__ + ": " + str(e) +")")


################################################################################
##########          Receiving a Json object
################################################################################
def _process_data(arg):
    """
    We received a Json object. It may be a JointsStream or a Hierarchy
    """
    size = str(sys.getsizeof(arg))
    _print_verbose("Paquet size:" + size, 2)
    _print_verbose(arg, 2)
    
    try:
        data = json.loads(arg)

        if data['Type'] == "Hierarchy":
            _process_hierarchy(data)
        elif data['Type'] == "JointsStream":
            _process_joints_stream(data)
        elif data['Type'] == "JointsUuids":
            _process_joints_uuids(data)
        else:
            _print_error("Unknown data type received: " + data['Type'])
    except ValueError:
        _print_verbose("Received a non-Json object." + sys.exc_info()[0] + sys.exc_info()[1], 1)
        return
    except Exception as e:
        _print_error("cannot process data (" + type(e).__name__ + ": " + str(e) +")")


################################################################################
##########          Hierarchy init
################################################################################
def _process_hierarchy(hierarchy_data):
    global JOINTS_BUFFER
    global JOINTS_INIT_ORIENT_INV_BUFFER
    global JOINTS_ROTATE_AXIS_INV_BUFFER
    global ROOTS_SYSTEM

    try:
        # First empty JOINTS_BUFFER
        JOINTS_BUFFER = {}
        JOINTS_INIT_ORIENT_INV_BUFFER = {}
        JOINTS_ROTATE_AXIS_INV_BUFFER = {}

        # Retrieve all joints from Maya and Transforms (we may be streaming to controllers too)
        all_maya_joints = pmc.ls(type="transform")

        # Then from all joints in the hierarchy, lookup in maya joints
        joints_name = hierarchy_data["Joints"]

        for joint_name in joints_name:
            # In Advanced Skeleton Joint's controllers are prefixed with 'FK'
            prefixedName = PREFIX_FK + joint_name
            # except for RooX_M which we want
            if joint_name == "RootX_M":
                prefixedName = joint_name
            # for the neck controller we want to map our joints to xtra joints
            if (joint_name == "Neck_M"):
                prefixedName = PREFIX_FKX + joint_name
            if (joint_name == "NeckPart1_M"):
                prefixedName = PREFIX_FKX + joint_name
            if (joint_name == "NeckPart2_M"):
                prefixedName = PREFIX_FKX + joint_name
            #---
            maya_joints = [maya_joint for maya_joint in all_maya_joints if maya_joint.name() == prefixedName]
            if maya_joints:
                # We should have one Maya joint mapped anyways
                if len(maya_joints) != 1:
                    _print_error("We should have 1 Maya joint mapped only. Taking the first one only.")
                
                maya_joint = maya_joints[0]
                _map_joint(joint_name, maya_joint)

        _send_ack_hierarchy_initialized()
        #_send_initial_mosketch_orient(False) #DEPRECATED and False is default anyway

        # Print nb joints in Maya and nb joints in BUFFER for information purposes
        _print_success("mapped " + str(len(JOINTS_BUFFER)) + " maya joints out of " + str(len(all_maya_joints)))
        _print_success("Buffers size: " + str(len(JOINTS_BUFFER)) + " / " + str(len(JOINTS_ROTATE_AXIS_INV_BUFFER)) + " / " + str(len(JOINTS_INIT_ORIENT_INV_BUFFER)))

    except Exception as e:
        _print_error("cannot process hierarchy data (" + type(e).__name__ + ": " + str(e) +")")
    #_send_inter_joints()
    _send_static_inter_joints()

    # Look for our root offset
    for maya_joint in all_maya_joints:
        if (maya_joint.name() == "FKOffsetRoot_M"):
            _print_verbose("we have our root pre transform", 1)
            ROOTS_SYSTEM[maya_joint.name()] = maya_joint
        elif (maya_joint.name() == "RootCenter_M"):
            _print_verbose("we have our root centre", 1)
            ROOTS_SYSTEM[maya_joint.name()] = maya_joint
        elif (maya_joint.name() == "RootSystem"):
            _print_verbose("we have our RootSystem", 1)
            ROOTS_SYSTEM[maya_joint.name()] = maya_joint


################################################################################
##########          Send joints that should be non sketchable
################################################################################
def _map_joint(mosketchName, maya_joint):
    #print "Found " + mosketchName
    JOINTS_BUFFER[mosketchName] = maya_joint
    vRO = maya_joint.getRotateAxis()
    RO = pmc.datatypes.EulerRotation(vRO[0], vRO[1], vRO[2]).asQuaternion()
    JOINTS_ROTATE_AXIS_INV_BUFFER[mosketchName] = RO.inverse()
    try:
        # We have a Joint => Get joint_orient into account
        JO = maya_joint.getOrientation().inverse()
        JOINTS_INIT_ORIENT_INV_BUFFER[mosketchName] = JO
        _print_verbose("j: " + mosketchName + " - " + maya_joint.name() + " " + str(RO[0]) + " " + str(RO[1]) + " " + str(RO[2]) + " " + str(RO[3]) + "; " + str(JO[0]) + " " + str(JO[1]) + " " + str(JO[2]) + " " + str(JO[3]), 2)
    except Exception:
        # We have a Transform => Do NOT get joint_orient into account but the initial transform instead
        JO = maya_joint.getRotation(space='transform', quaternion=True).inverse()
        JOINTS_INIT_ORIENT_INV_BUFFER[mosketchName] = JO
        _print_verbose("t: " + mosketchName + " - " + maya_joint.name() + " " + str(RO[0]) + " " + str(RO[1]) + " " + str(RO[2]) + " " + str(RO[3]) + "; " + str(JO[0]) + " " + str(JO[1]) + " " + str(JO[2]) + " " + str(JO[3]), 2)


################################################################################
##########          Send joints that should be non sketchable
################################################################################
def _send_inter_joints():
    global JOINTS_BUFFER
    global INTER_JOINTS_BUFFER
    #print "_send_inter_joints"
    all_maya_joints = pmc.ls(type="joint")
    joints_buffer_values = JOINTS_BUFFER.values()
    for maya_joint in all_maya_joints:
        index = 0
        found = False
        for moJoint in joints_buffer_values:
            if "FK" + maya_joint.name() == moJoint.name():
                #print "Found " + moJoint.name()
                last_name = moJoint.name()
                found = True
                break
            else:
                index = index + 1
        if found == True:
            joints_buffer_values.remove(last_name)
        else:
            INTER_JOINTS_BUFFER[maya_joint.name()] = maya_joint
            print "+Inter " + INTER_JOINTS_BUFFER[maya_joint.name()].name() + " n= " + str(len(joints_buffer_values))
    print "Total inter joints found: " + str(len(INTER_JOINTS_BUFFER))
    all_values = INTER_JOINTS_BUFFER.values()
    joints_stream = {}
    joints_stream[JSON_KEY_TYPE] = "InterJoints"
    joints_stream[JSON_KEY_JOINTS] = []
    for maya_joint in all_values:
        joint_data = {} # Reinit it
        joint_data[JSON_KEY_NAME] = maya_joint.name()
        joints_stream[JSON_KEY_JOINTS].append(joint_data)
        #print "Appending " + str(joint_data[JSON_KEY_NAME])
    json_data = json.dumps(joints_stream)
    CONNECTION.write(json_data)


################################################################################
##########          Send joints that should be non sketchable
################################################################################
def _send_static_inter_joints():
    joints_stream = {}
    joints_stream[JSON_KEY_TYPE] = "InterJoints"
    joints_stream[JSON_KEY_JOINTS] = []
    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "HipPart1_L"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "HipPart2_L"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ShoulderPart1_L"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ShoulderPart2_L"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ElbowPart1_L"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ElbowPart2_L"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "RootPart1_M"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "RootPart2_M"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "NeckPart1_M"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "NeckPart2_M"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "HipPart1_R"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "HipPart2_R"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ShoulderPart1_R"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ShoulderPart2_R"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ElbowPart1_R"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    joint_data = {} # Reinit it
    joint_data[JSON_KEY_NAME] = "ElbowPart2_R"
    joints_stream[JSON_KEY_JOINTS].append(joint_data)

    json_data = json.dumps(joints_stream)
    CONNECTION.write(json_data)


################################################################################
##########          We receive joints
################################################################################
def _process_joints_stream(joints_stream_data):
    '''
    We receive "full" local rotations and local translations.
    So we need to substract rotate axis and joint orient.
    '''
    global JOINTS_BUFFER
    global JOINTS_INIT_ORIENT_INV_BUFFER
    global JOINTS_ROTATE_AXIS_INV_BUFFER

    global JSON_KEY_NAME
    global JSON_KEY_ANATOMIC
    global JSON_KEY_ROTATION
    global JSON_KEY_TRANSLATION

    try:
        joints_data = joints_stream_data["Joints"]
        _print_verbose(joints_data, 3)

        for joint_data in joints_data:
            # We select all joints having the given name
            joint_name = joint_data[JSON_KEY_NAME]
            try:
                maya_joint = JOINTS_BUFFER[joint_name]
            except KeyError:
                continue

            if maya_joint:
                quat = pmc.datatypes.Quaternion(joint_data[JSON_KEY_ROTATION])
                # W = [S] * [RO] * [R] * [JO] * [IS] * [T]
                RO = JOINTS_ROTATE_AXIS_INV_BUFFER[joint_name]
                JO = JOINTS_INIT_ORIENT_INV_BUFFER[joint_name]
                if (joint_name == "RootX_M"):
                    # The root controller has an pre transform
                    offset = ROOTS_SYSTEM["FKOffsetRoot_M"];
                    #offset = ROOTS_SYSTEM["RootSystem"];
                    #axis = offset.getRotateAxis()
                    #oRO = pmc.datatypes.EulerRotation(axis[0], axis[1], axis[2]).asQuaternion()
                    oJO = offset.getRotation(space='transform', quaternion=True)
                    quat = oJO.inverse() * RO * quat * JO * oJO
                else:
                    quat = RO * quat * JO
                maya_joint.setRotation(quat, space='transform')
                
                joint_type = joint_data[JSON_KEY_ANATOMIC]                
                if joint_type == 7: # This is a 6 DoFs joint so consider translation part too
                    trans = pmc.datatypes.Vector(joint_data[JSON_KEY_TRANSLATION])
                    trans = trans.rotateBy(RO)
                    # Mosketch uses meters. Maya uses centimeters
                    trans *= 100
                    if (joint_name == "RootX_M"):
                        offset = ROOTS_SYSTEM["RootCenter_M"];
                        #offset = ROOTS_SYSTEM["FKOffsetRoot_M"];
                        #offset = ROOTS_SYSTEM["RootSystem"];
                        oT = offset.getTranslation(space='transform')
                        trans -= oT
                    maya_joint.setTranslation(trans, space='transform')

        _send_ack_jointstream_received()
    except KeyError as e:
        _print_error("cannot find " + joint_name + " in maya")
        return
    except Exception as e:
        _print_error("cannot process joints stream (" + type(e).__name__ + ": " + str(e) +")")


################################################################################
##########          Send Mosketch initial orientation Mode
#                   DEPRECATED
################################################################################
def _send_initial_mosketch_orient(orientMode):
    packet = {}
    packet[JSON_KEY_TYPE] = "OrientMode"
    packet[JSON_KEY_MODE] = orientMode
    json_data = json.dumps(packet)
    CONNECTION.write(json_data)
    CONNECTION.flush() # You need to flush so it's not concatenated with another packet.
    _print_verbose("_send_initial_mosketch_orient", 1)


################################################################################
##########          Receiving all the Mosketch's joints uuids
################################################################################
def _process_joints_uuids(data):
    _print_verbose("_process_joints_uuids", 1)
    global JOINTS_UUIDS

    try:
        joints_data = data[JSON_KEY_JOINTS]
        _print_verbose(joints_data, 3)

        for joint_data in joints_data:
            for name in joint_data:
                JOINTS_UUIDS[name] = joint_data[name]
                #print name + ':' + JOINTS_UUIDS[name]

    except Exception as e:
        _print_error("cannot process joints uuids (" + type(e).__name__ + ": " + str(e) +")")

    print "Total uuids: " + str(len(JOINTS_UUIDS))
