# coding: utf-8
# Note: some 6 DoFs joints may have initial rotation too. So take this into account
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
import socket

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
SCRIPT_VER = "0.56"
MAIN_WINDOW = None
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
JSON_KEY_OBJECT = "object"
JSON_KEY_COMMAND = "command"
JSON_KEY_PARAMETERS = "parameters"

# Packet Type
PACKET_TYPE_COMMAND = "NetCommand"

# MAYA JOINTS BUFFERS
JOINTS_BUFFER = {}
JOINTS_INIT_ORIENT_INV_BUFFER = {}
JOINTS_ROTATE_AXIS_INV_BUFFER = {}
INTER_JOINTS_BUFFER = {}
JOINTS_UUIDS = {}
CONTROLLERS_BUFFER = {}
CONTROLLERS_INIT_ORIENT_INV_BUFFER = {}
CONTROLLERS_ROTATE_AXIS_INV_BUFFER = {}

# Verbose level (1 for critical informations, 3 to output all packets)
VERBOSE = 1

# Some models have pre transform we need to take into account
ROOTS_SYSTEM = {}

# RIG Prefix (usually for Advanced Skeleton)
PREFIX_FKX = ""
PREFIX_FK = ""

################################################################################
# Define a model name to perform specific actions
################################################################################
MODEL_NAME = "Mosko_noRig"
#MODEL_NAME = "Mosko_Rigged"
#MODEL_NAME = "DeepSea_Rigged"


################################################################################
# Array of DeepSea joints name that need FKX prefix instead of FK
################################################################################
DEEPSEA_FKX_BIND = [
  "BodyFinSide2_L", "BodyFinSide2Part1_L", "BodyFinSide2Part2_L", "BodyFinSide3_L", "BodyFinSide3Part1_L", "BodyFinSide3Part2_L",
  "finSide_L", "finSidePart1_L", "finSidePart2_L", "finSide2_L", "finSide2Part1_L", "finSide2Part2_L",
  "finSide4_L", "finSide4Part1_L", "finSide4Part2_L", "BodyFinLowerA_L", "BodyFinLowerAPart1_L", "BodyFinLowerAPart2_L",
  "BodyFinLowerA1_L", "BodyFinLowerA1Part1_L", "BodyFinLowerA1Part2_L", "BodyFinLowerB_L", "BodyFinLowerBPart1_L", "BodyFinLowerBPart2_L",
  "BodyFinLowerB1_L", "BodyFinLowerB1Part1_L", "BodyFinLowerB1Part2_L", "BackE_M", "BackEPart1_M", "BackEPart2_M", "BackEPart3_M", "BackEPart4_M",
  "tailMain1_M", "tailMain1Part1_M", "tailMain1Part2_M", "tailMain1Part3_M", "tailMain1Part4_M", "tailMain2_M", "tailMain2Part1_M",
  "tailMain2Part2_M", "tailMain2Part3_M", "tailMain2Part4_M", "tailMain3_M", "tailMain3Part1_M", "tailMain3Part2_M", "tailMain3Part3_M",
  "tailMain3Part4_M", "tailMain4_M", "tailMain4Part1_M", "tailMain4Part2_M", "tailMain4Part3_M", "tailMain4Part4_M",
  "BodyFinUpper4_M", "BodyFinUpper4Part1_M", "BodyFinUpper4Part2_M", "BodyFinUpper5_M", "BodyFinUpper5Part1_M", "BodyFinUpper5Part2_M",
  "bodyFinUpper1_M", "bodyFinUpper1Part1_M", "bodyFinUpper2_M", "bodyFinUpper2Part1_M", "BodyFinUpper1_M", "BodyFinUpper1Part1_M",
  "BodyFinUpper2_M", "BodyFinUpper2Part1_M", "BodyFinSide2_R", "BodyFinSide2Part1_R", "BodyFinSide2Part2_R", "BodyFinSide3_R",
  "BodyFinSide3Part1_R", "BodyFinSide3Part2_R", "finSide_R", "finSidePart1_R", "finSidePart2_R", "finSide2_R", "finSide2Part1_R", "finSide2Part2_R",
  "finSide4_R", "finSide4Part1_R", "finSide4Part2_R", "BodyFinLowerA_R", "BodyFinLowerAPart1_R", "BodyFinLowerAPart2_R", "BodyFinLowerA1_R",
  "BodyFinLowerA1Part1_R", "BodyFinLowerA1Part2_R", "BodyFinLowerB_R", "BodyFinLowerBPart1_R", "BodyFinLowerBPart2_R",
  "BodyFinLowerB1_R", "BodyFinLowerB1Part1_R", "BodyFinLowerB1Part2_R"
]


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
                    command='import mosketch_for_maya;reload(mosketch_for_maya);mosketch_for_maya.start("noRig")')
    pmc.shelfButton(label='Stop',
                    parent=shelf_layout,
                    image1=stop_icon_name,
                    command='mosketch_for_maya.stop()')


################################################################################
# shelf start button
#in model_name must be a string to specify a model
################################################################################
def start(model_name):
    """
    Call this function from Maya (in a shelf button or in script editor for example):
        import mosketch_for_maya
        mosketch_for_maya.start("noRig")
        model_name can be "" or "noRig" for non-rigged characters
          "Rig" for Mosko_Rigged
          "Deep" for DeepSea_Rigged
    """
    global MODEL_NAME

    if (model_name == 'noRig'):
        MODEL_NAME = 'Mosko_noRig'
    elif (model_name == 'Rig'):
        MODEL_NAME = 'Mosko_Rigged'
    elif (model_name == 'Deep'):
        MODEL_NAME = 'DeepSea_Rigged'
    print 'Model name = ' + MODEL_NAME
    _create_gui()


################################################################################
# shelf stop button
################################################################################
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
# Class definition for UI
################################################################################
class UI_MosketchWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        maya_window = _get_maya_main_window()
        super(UI_MosketchWindow, self).__init__(maya_window)

    def init_mosketch_ui(self):
        print "Init UI window"
        self.setWindowTitle(MODEL_NAME + SCRIPT_VER)

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

        self.status_text = QtWidgets.QLabel(content)
        self.status_text.setWordWrap(True)
        self.status_text.setText("Not connected yet")

        content.setLayout(main_layout)
        main_layout.addWidget(help_text)
        main_layout.addLayout(ip_layout)
        main_layout.addLayout(buttons_layout)
        self.setCentralWidget(content)
        main_layout.addSpacerItem(spacer)
        main_layout.addWidget(self.status_text)

    def closeEvent(self, event):
        # Close connection if any is still opened
        if CONNECTION is not None:
          _close_connection()


################################################################################
##########          GUI
################################################################################
def _create_gui():
    global MAIN_WINDOW
    
    MAIN_WINDOW = UI_MosketchWindow()
    MAIN_WINDOW.init_mosketch_ui()
    MAIN_WINDOW.show()    

    _print_verbose(sys.version, 1)
    _print_verbose(sys.getdefaultencoding(), 2)
    _print_verbose(sys.getfilesystemencoding(), 2)
    _print_verbose(sys.prefix, 2)
    _print_verbose(locale.getdefaultlocale(), 2)
    

################################################################################
##########          Destroy GUI
################################################################################
def _destroy_gui():
    MAIN_WINDOW.close()


################################################################################
##########          Return main window
################################################################################
def _get_maya_main_window():
    OpenMayaUI.MQtUtil.mainWindow()
    ptr = OpenMayaUI.MQtUtil.mainWindow()
    if ptr is None:
        raise RuntimeError('No Maya window found.')

    window = wrapInstance(long(ptr), QtWidgets.QMainWindow)
    assert isinstance(window, QtWidgets.QMainWindow)
    return window


################################################################################
##########          Change IP text
################################################################################
def _ip_text_changed(text):
    global IP
    IP = text


################################################################################
##########          Helpers
################################################################################
def _print_error(error):
    error_msg = "ERROR: " + error
    print error_msg
    MAIN_WINDOW.status_text.setText(error_msg)

def _print_success(success):
    success_msg = "SUCCESS: " + success
    print success_msg
    MAIN_WINDOW.status_text.setText(success_msg)

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

    # Test IP format
    if (is_valid_ipv4_address(IP) == False):
        _print_error('IP address looks wrong, please enter a valid IP address')
        return
    else:
        _print_success('Connecting to ' + IP)

    # Perform initial settings (pre connection)
    _initial_settings()

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

    # Useless to prepare the data if we have no connection
    if CONNECTION is None:
        _print_error("Mosketch is not connected!")
        return

    if ((MODEL_NAME == "Mosko_Rigged") or (MODEL_NAME == "DeepSea_Rigged")):
        _update_mosketch_from_controllers()
        return

    # For every joint, pack data, then send packet
    try:
        quat = pmc.datatypes.Quaternion()
        joints_buffer_values = JOINTS_BUFFER.values()
        joints_stream = {}
        joints_stream[JSON_KEY_TYPE] = "JointsStream"
        joints_stream[JSON_KEY_JOINTS] = []
        for maya_joint in joints_buffer_values:
            joint_data = {} # Reinit it
            joint_name = maya_joint.name()

            joint_data[JSON_KEY_NAME] = joint_name # Fill the Json key for the name

            # W = [S] * [RO] * [R] * [JO] * [IS] * [T]
            RO = JOINTS_ROTATE_AXIS_INV_BUFFER[joint_name].inverse()
            JO = JOINTS_INIT_ORIENT_INV_BUFFER[joint_name].inverse()
            quat = maya_joint.getRotation(space='transform', quaternion=True)
            quat = RO * quat * JO
            joint_data[JSON_KEY_ROTATION] = [quat[0], quat[1], quat[2], quat[3]]

            translation = maya_joint.getTranslation(space='transform')
            translation *= 0.01 # Mosketch uses meters. Maya uses centimeters
            joint_data[JSON_KEY_TRANSLATION] = [translation[0], translation[1], translation[2]]
            joints_stream[JSON_KEY_JOINTS].append(joint_data)
        json_data = json.dumps(joints_stream)
        CONNECTION.write(json_data)
    except Exception, e:
        _print_error("cannot send joint value (" + str(e) + ")")


################################################################################
##########          SEND CONTROLLERS
################################################################################
def _update_mosketch_from_controllers():
    '''
    We send "full" local rotations and local translations.
    So we need to add rotate axis and joint orient.
    '''
    # For every joint, pack data, then send packet
    try:
        quat = pmc.datatypes.Quaternion()
        joints_buffer_values = CONTROLLERS_BUFFER.values()
        joints_stream = {}
        joints_stream[JSON_KEY_TYPE] = "JointsStream"
        joints_stream[JSON_KEY_JOINTS] = []
        for maya_joint in joints_buffer_values:
            joint_data = {} # Reinit it
            idx_name = maya_joint.name()

            if ((MODEL_NAME == "Mosko_Rigged") or (MODEL_NAME == "DeepSea_Rigged")):
              if idx_name.startswith(PREFIX_FKX):
                  idx_name = idx_name.replace(PREFIX_FKX, "", 1)
              elif idx_name.startswith(PREFIX_FK):
                  idx_name = idx_name.replace(PREFIX_FK, "", 1)
              elif idx_name == "RootX_M":
                  joint_data[JSON_KEY_NAME] = idx_name # Fill the Json key for the name
                  # For this controller we need to take an offset into account
                  if (MODEL_NAME == "Mosko_Rigged"):
                      offset = ROOTS_SYSTEM["RootCenter_M"]
                  elif (MODEL_NAME == "DeepSea_Rigged"):
                      offset = ROOTS_SYSTEM["RootOffsetX_M"]
                  oT = offset.getTranslation(space='transform')
                  # The root controller has a pre transform
                  offset = ROOTS_SYSTEM["FKOffsetRoot_M"]
                  oJO = offset.getRotation(space='transform', quaternion=True)
                  RO = CONTROLLERS_ROTATE_AXIS_INV_BUFFER[idx_name].inverse()
                  JO = CONTROLLERS_INIT_ORIENT_INV_BUFFER[idx_name].inverse()
                  quat = maya_joint.getRotation(space='transform', quaternion=True)
                  quat = oJO * RO * quat * JO * oJO.inverse()
                  joint_data[JSON_KEY_ROTATION] = [quat[0], quat[1], quat[2], quat[3]]

                  translation = maya_joint.getTranslation(space='transform')
                  translation += oT
                  translation *= 0.01 # Mosketch uses meters. Maya uses centimeters
                  joint_data[JSON_KEY_TRANSLATION] = [translation[0], translation[1], translation[2]]
                  joints_stream[JSON_KEY_JOINTS].append(joint_data)
                  continue

            joint_data[JSON_KEY_NAME] = idx_name # Fill the Json key for the name

            # W = [S] * [RO] * [R] * [JO] * [IS] * [T]
            RO = CONTROLLERS_ROTATE_AXIS_INV_BUFFER[idx_name].inverse()
            JO = CONTROLLERS_INIT_ORIENT_INV_BUFFER[idx_name].inverse()
            quat = maya_joint.getRotation(space='transform', quaternion=True)
            quat = RO * quat * JO
           
            #extra = _compute_extra(idx_name)
            #quat = extra*quat

            joint_data[JSON_KEY_ROTATION] = [quat[0], quat[1], quat[2], quat[3]]

            translation = maya_joint.getTranslation(space='transform')
            translation *= 0.01 # Mosketch uses meters. Maya uses centimeters
            joint_data[JSON_KEY_TRANSLATION] = [translation[0], translation[1], translation[2]]
            joints_stream[JSON_KEY_JOINTS].append(joint_data)
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
        json_data = json.dumps([ack_packet])
        CONNECTION.write(json_data)
        CONNECTION.flush()
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
        ack_packet[JSON_KEY_TYPE] = "JointsStreamAck"
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
        - Type == "JointsUuids" => Receiving Mosketch UUIDs for all joints
        - Type == "NetCommand" => Packet type to send Mosketch commands
    """
    try:
        raw_data = CONNECTION.readLine()
        
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

        if data[JSON_KEY_TYPE] == "Hierarchy":
            _process_hierarchy(data)
        elif data[JSON_KEY_TYPE] == "JointsStream":
            _process_joints_stream(data)
        elif data[JSON_KEY_TYPE] == "JointsUuids":
            _process_joints_uuids(data)
        else:
            _print_error("Unknown data type received: " + data[JSON_KEY_TYPE])
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
    global CONTROLLERS_BUFFER
    global CONTROLLERS_INIT_ORIENT_INV_BUFFER
    global CONTROLLERS_ROTATE_AXIS_INV_BUFFER

    try:
        # First empty JOINTS_BUFFER
        JOINTS_BUFFER = {}
        JOINTS_INIT_ORIENT_INV_BUFFER = {}
        JOINTS_ROTATE_AXIS_INV_BUFFER = {}
        CONTROLLERS_BUFFER = {}
        CONTROLLERS_INIT_ORIENT_INV_BUFFER = {}
        CONTROLLERS_ROTATE_AXIS_INV_BUFFER = {}

        # Retrieve all joints from Maya and Transforms (we may be streaming to controllers too)
        all_maya_joints = pmc.ls(type="joint")
        all_maya_transform = pmc.ls(type="transform")

        # Then from all joints in the hierarchy, lookup in maya joints
        joints_name = hierarchy_data["Joints"]

        for joint_name in joints_name:
            # In Advanced Skeleton Joint's controllers are prefixed with 'FK'
            prefixed_name = PREFIX_FK + joint_name
            # except for RooX_M which we want as is
            if joint_name == "RootX_M":
                prefixed_name = joint_name
            # We are also missing controllers for end toes in Mosko, so we plug joint onto joint
            if (MODEL_NAME == "Mosko_Rigged"):
                if (joint_name == 'ToesEnd_L'):
                    prefixed_name = 'ToesEnd_L'
                if (joint_name == 'ToesEnd_R'):
                    prefixed_name = 'ToesEnd_R'
            if (MODEL_NAME == "DeepSea_Rigged"):
                prefixed_name = _deepsea_controllers(joint_name)

            # We store joints in any cases
            maya_real_joints = [maya_joint for maya_joint in all_maya_joints if maya_joint.name() == joint_name]
            if maya_real_joints:
                # We should have one Maya joint mapped anyways
                if len(maya_real_joints) != 1:
                    _print_error("We should have 1 Maya joint mapped only. Taking the first one only.")                
                _map_joint(joint_name, maya_real_joints[0])

            # Then we store controllers, there might be somle joints too for simplicity
            maya_joints = [maya_joint for maya_joint in all_maya_transform if maya_joint.name() == prefixed_name]
            if maya_joints:
                # We should have one Maya joint mapped anyways
                if len(maya_joints) != 1:
                    _print_error("We should have 1 Maya joint mapped only. Taking the first one only.")
                _map_controller(joint_name, maya_joints[0])

        # If no mapping close connection
        if (len(JOINTS_BUFFER) == 0):
            _close_connection()
            _print_error("Couldn't map joints. Check Maya's namespaces maybe.")
            return

        _send_ack_hierarchy_initialized()

        # Print nb joints in Maya and nb joints in BUFFER for information purposes
        _print_success("mapped " + str(len(JOINTS_BUFFER)) + " maya joints out of " + str(len(all_maya_transform)))
        _print_success("Buffers size: " + str(len(JOINTS_BUFFER)) + " / " + str(len(JOINTS_ROTATE_AXIS_INV_BUFFER)) + " / " + str(len(JOINTS_INIT_ORIENT_INV_BUFFER)))
        _print_verbose('Joints buffer = ' + str(len(JOINTS_BUFFER)) + ', controllers buffer = ' + str(len(CONTROLLERS_BUFFER)), 1)

    except Exception as e:
        _print_error("cannot process hierarchy data (" + type(e).__name__ + ": " + str(e) +")")
    #_send_static_inter_joints() # Example to send multiple joints as non sketchable

    # Send orientation mode
    if (MODEL_NAME == "Mosko_noRig"):
        _send_command_orientMode(1)
    elif (MODEL_NAME == "Mosko_Rigged"):
        _send_command_orientMode(0)

    # Sepcify in which space we want to work. Default is Local
    _send_command_jointSpace("Local")
    #_send_command_jointSpace("World")

    # Look for our root offset
    _fill_root_system()


################################################################################
##########          This is filling arrays to map Mosketch name to a Maya joint or transform
################################################################################
def _map_joint(mosketch_name, maya_joint):
    JOINTS_BUFFER[mosketch_name] = maya_joint
    vRO = maya_joint.getRotateAxis()
    RO = pmc.datatypes.EulerRotation(vRO[0], vRO[1], vRO[2]).asQuaternion()
    JOINTS_ROTATE_AXIS_INV_BUFFER[mosketch_name] = RO.inverse()
    try:
        # We have a Joint => Get joint_orient into account
        JO = maya_joint.getOrientation().inverse()
        JOINTS_INIT_ORIENT_INV_BUFFER[mosketch_name] = JO
        _print_verbose("j: " + mosketch_name + " - " + maya_joint.name() + " " + str(RO[0]) + " " + str(RO[1]) + " " + str(RO[2]) + " " + str(RO[3]) + "; " + str(JO[0]) + " " + str(JO[1]) + " " + str(JO[2]) + " " + str(JO[3]), 2)
    except Exception:
        # We have a Transform => Do NOT get joint_orient into account but the initial transform instead
        JO = maya_joint.getRotation(space='transform', quaternion=True).inverse()
        JOINTS_INIT_ORIENT_INV_BUFFER[mosketch_name] = JO
        #_print_verbose("t: " + mosketch_name + " - " + maya_joint.name() + " " + str(RO[0]) + " " + str(RO[1]) + " " + str(RO[2]) + " " + str(RO[3]) + "; " + str(JO[0]) + " " + str(JO[1]) + " " + str(JO[2]) + " " + str(JO[3]), 2)
        _print_verbose("WARNING: we have a controller while we should have a joint: " + mosketch_name + " - " + maya_joint.name(), 1)


################################################################################
##########          This is filling arrays to map Mosketch name to a Maya controller
################################################################################
def _map_controller(mosketch_name, maya_controller):
    CONTROLLERS_BUFFER[mosketch_name] = maya_controller
    vRO = maya_controller.getRotateAxis()
    RO = pmc.datatypes.EulerRotation(vRO[0], vRO[1], vRO[2]).asQuaternion()
    CONTROLLERS_ROTATE_AXIS_INV_BUFFER[mosketch_name] = RO.inverse()
    try:
        # We have a Joint => Get joint_orient into account
        JO = maya_controller.getOrientation().inverse()
        CONTROLLERS_INIT_ORIENT_INV_BUFFER[mosketch_name] = JO
        _print_verbose("WARNING: we have a joint while we should have a controller: " + mosketch_name + " - " + maya_controller.name(), 2)
    except Exception:
        # We have a Transform => Do NOT get joint_orient into account but the initial transform instead
        JO = maya_controller.getRotation(space='transform', quaternion=True).inverse()
        CONTROLLERS_INIT_ORIENT_INV_BUFFER[mosketch_name] = JO
        _print_verbose("t: " + mosketch_name + " - " + maya_controller.name() + " " + str(RO[0]) + " " + str(RO[1]) + " " + str(RO[2]) + " " + str(RO[3]) + "; " + str(JO[0]) + " " + str(JO[1]) + " " + str(JO[2]) + " " + str(JO[3]), 2)


################################################################################
##########          Send joints that should be non sketchable in one big message
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

    if ((MODEL_NAME == "Mosko_Rigged") or (MODEL_NAME == "DeepSea_Rigged")):
        _process_controllers_stream(joints_stream_data)
        return

    try:
        joints_data = joints_stream_data[JSON_KEY_JOINTS]
        _print_verbose(joints_data, 3)

        for joint_data in joints_data:
            # We select all joints having the given name
            joint_name = joint_data[JSON_KEY_NAME]
            try:
                maya_joint = JOINTS_BUFFER[joint_name]
            except KeyError:
                continue

            if maya_joint:
                # W = [S] * [RO] * [R] * [JO] * [IS] * [T]
                quat = pmc.datatypes.Quaternion(joint_data[JSON_KEY_ROTATION])
                rotate_axis_inv = JOINTS_ROTATE_AXIS_INV_BUFFER[joint_name]
                joint_orient_inv = JOINTS_INIT_ORIENT_INV_BUFFER[joint_name]
                quat = rotate_axis_inv * quat * joint_orient_inv
                maya_joint.setRotation(quat, space='transform')
                
                joint_type = joint_data[JSON_KEY_ANATOMIC]                
                if joint_type == 7: # This is a 6 DoFs joint so consider translation part too
                    trans = pmc.datatypes.Vector(joint_data[JSON_KEY_TRANSLATION])
                    trans = trans.rotateBy(rotate_axis_inv)
                    # Mosketch uses meters. Maya uses centimeters
                    trans *= 100
                    maya_joint.setTranslation(trans, space='transform')

        _send_ack_jointstream_received()
    except KeyError as e:
        _print_error("cannot find " + joint_name + " in maya")
        return
    except Exception as e:
        _print_error("cannot process joints stream (" + type(e).__name__ + ": " + str(e) +")")


################################################################################
##########          We receive joints but we use name mapping
################################################################################
def _process_controllers_stream(joints_stream_data):
    '''
    We receive "full" local rotations and local translations.
    So we need to substract rotate axis and joint orient.
    '''
    global CONTROLLERS_BUFFER
    global CONTROLLERS_INIT_ORIENT_INV_BUFFER
    global CONTROLLERS_ROTATE_AXIS_INV_BUFFER

    try:
        joints_data = joints_stream_data[JSON_KEY_JOINTS]
        _print_verbose(joints_data, 3)

        for joint_data in joints_data:
            # We select all joints having the given name
            joint_name = joint_data[JSON_KEY_NAME]
            try:
                maya_controller = CONTROLLERS_BUFFER[joint_name]
            except KeyError:
                #_print_error("cannot find " + joint_name + " in controllers")
                continue

            if maya_controller:
                # W = [S] * [RO] * [R] * [JO] * [IS] * [T]
                quat = pmc.datatypes.Quaternion(joint_data[JSON_KEY_ROTATION])
                rotate_axis_inv = CONTROLLERS_ROTATE_AXIS_INV_BUFFER[joint_name]
                orient_inv = CONTROLLERS_INIT_ORIENT_INV_BUFFER[joint_name]

                if (joint_name == "RootX_M"):
                    # The root controller has a pre transform
                    offset = ROOTS_SYSTEM["FKOffsetRoot_M"];
                    oJO = offset.getRotation(space='transform', quaternion=True)
                    quat = oJO.inverse() * rotate_axis_inv * quat * orient_inv * oJO
                    maya_controller.setRotation(quat, space='transform')
                else:
                    #extra = _compute_extra(joint_name)
                    #quat = quat * extra.inverse()
                    quat = rotate_axis_inv * quat * orient_inv
                    maya_controller.setRotation(quat, space='transform')
                
                joint_type = joint_data[JSON_KEY_ANATOMIC]                
                if joint_type == 7: # This is a 6 DoFs joint so consider translation part too
                    trans = pmc.datatypes.Vector(joint_data[JSON_KEY_TRANSLATION])
                    trans = trans.rotateBy(rotate_axis_inv)
                    # Mosketch uses meters. Maya uses centimeters
                    trans *= 100

                    if (MODEL_NAME == 'Mosko_Rigged'):
                        if (joint_name == "RootX_M"):
                            offset = ROOTS_SYSTEM["RootCenter_M"];#Todo: Give uniq name (left as is for example/clarity purpose)
                            oT = offset.getTranslation(space='transform')
                            trans -= oT
                    elif (MODEL_NAME == 'DeepSea_Rigged'):
                        if (joint_name == "RootX_M"):
                            offset = ROOTS_SYSTEM["RootOffsetX_M"];#Todo: Give uniq name (left as is for example/clarity purpose)
                            oT = offset.getTranslation(space='transform')
                            trans -= oT

                    maya_controller.setTranslation(trans, space='transform')

        _send_ack_jointstream_received()
    except KeyError as e:
        _print_error("cannot find " + joint_name + " in maya")
        return
    except Exception as e:
        _print_error("cannot process joints stream (" + type(e).__name__ + ": " + str(e) +")")


################################################################################
##########          Send Mosketch initial orientation Mode through a command
#in orient_mode [0 or 1]
################################################################################
def _send_command_orientMode(orient_mode):
    global CONNECTION
    packet = {}
    packet[JSON_KEY_TYPE] = PACKET_TYPE_COMMAND
    packet[JSON_KEY_OBJECT] = 'scene'
    packet[JSON_KEY_COMMAND] = 'setStreamingJointOrientMode'

    jsonObj = {}
    jsonObj['jointOrientMode'] = str(orient_mode)
    packet[JSON_KEY_PARAMETERS] = jsonObj # we need parameters to be a json object

    json_data = json.dumps([packet]) # [] specific for commands that could be buffered
    CONNECTION.write(json_data)
    CONNECTION.flush()
    _print_verbose("_send_command_orientMode", 1)


################################################################################
##########          Set wireframe visibility in Mosketch through a command
#in visible [true or false]
################################################################################
def _send_command_wireframe(visible):
    global CONNECTION
    packet = {}
    packet[JSON_KEY_TYPE] = PACKET_TYPE_COMMAND
    packet[JSON_KEY_OBJECT] = 'scene'
    packet[JSON_KEY_COMMAND] = 'setWireframeVisibility'

    jsonObj = {}
    jsonObj['visible'] = visible
    packet[JSON_KEY_PARAMETERS] = jsonObj # we need parameters to be a json object

    json_data = json.dumps([packet]) # [] specific for commands that could be buffered
    CONNECTION.write(json_data)
    CONNECTION.flush()
    _print_verbose("_send_command_wireframe", 1)


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

    except Exception as e:
        _print_error("cannot process joints uuids (" + type(e).__name__ + ": " + str(e) +")")

    print "Total uuids: " + str(len(JOINTS_UUIDS))
    
    #NEXT SECTION: Test/desmonstrate the use of Mosketch commands
    #_send_command_selectJoint('Wrist_L')
    #_send_command_wireframe('true')
    #_send_command_setSketchable(JOINTS_UUIDS['Spine2_M'], 'false')
    #_send_command_setSketchable(JOINTS_UUIDS['Spine3_M'], 'false')
    #Test selecting joints and adding effectors
    #_send_command_selectJoint('Toes_L', '1')
    #_send_command_selectJoint('Toes_R', '0')
    #_send_command_addEffector()


################################################################################
##########          Set a joint sketchable through a command
#in uuid
#in sketchable [true or false]
################################################################################
def _send_command_setSketchable(uuid, sketchable):
    global CONNECTION
    packet = {}
    packet[JSON_KEY_TYPE] = PACKET_TYPE_COMMAND
    packet[JSON_KEY_OBJECT] = 'joint'
    packet[JSON_KEY_COMMAND] = 'setSketchable'

    jsonObj = {}
    jsonObj['uuid'] = uuid
    jsonObj['sketchable'] = sketchable
    packet[JSON_KEY_PARAMETERS] = jsonObj # we need parameters to be a json object

    json_data = json.dumps([packet]) # [] specific for commands that could be buffered
    CONNECTION.write(json_data)
    CONNECTION.flush()
    _print_verbose("_send_command_setSketchable", 1)


################################################################################
##########          Select a joint by name through a command
#in joint_name
################################################################################
def _send_command_selectJoint(joint_name):
    global CONNECTION

    try:
        uuid = JOINTS_UUIDS[joint_name]
    except Exception as e:
        _print_error("cannot find joint uuid for (" + type(e).__name__ + ": " + str(e) +")")
        return

    packet = {}
    packet[JSON_KEY_TYPE] = PACKET_TYPE_COMMAND
    packet[JSON_KEY_OBJECT] = 'scene'
    packet[JSON_KEY_COMMAND] = 'selectByUuid'

    jsonObj = {}
    jsonObj['uuid'] = uuid
    jsonObj['eraseGroup'] = '1' # '0' or '1'
    jsonObj['toggleIfSelected'] = '1' # '0' or '1'
    packet[JSON_KEY_PARAMETERS] = jsonObj # we need parameters to be a json object

    json_data = json.dumps([packet]) # [] specific for commands that could be buffered
    CONNECTION.write(json_data)
    CONNECTION.flush()
    _print_verbose("_send_command_selectJoint", 1)


################################################################################
##########          Add position effectors to selected joints
################################################################################
def _send_command_addEffector():
    global CONNECTION

    packet = {}
    packet[JSON_KEY_TYPE] = PACKET_TYPE_COMMAND
    packet['object'] = 'scene'
    packet['command'] = 'attachNumIKEffector'

    jsonObj = {}
    packet['parameters'] = jsonObj # we need parameters to be a json object

    json_data = json.dumps([packet]) # [] specific for commands that could be buffered
    CONNECTION.write(json_data)
    CONNECTION.flush()
    _print_verbose("_send_command_addEffector", 1)


################################################################################
##########          Set if we want Mosketch transform in local or world space
#in space_mode ["Local" or "World"]
################################################################################
def _send_command_jointSpace(space_mode):
    global CONNECTION

    packet = {}
    packet[JSON_KEY_TYPE] = PACKET_TYPE_COMMAND
    packet['object'] = 'scene'
    packet['command'] = 'setStreamingJointSpace'

    jsonObj = {}
    jsonObj['jointSpace'] = str(space_mode)
    packet[JSON_KEY_PARAMETERS] = jsonObj # we need parameters to be a json object

    json_data = json.dumps([packet]) # [] specific for commands that could be buffered
    CONNECTION.write(json_data)
    CONNECTION.flush()
    _print_verbose("_send_command_jointSpace", 1)


################################################################################
##########          Set initial states according to the model (pre connection)
################################################################################
def _initial_settings():
    global MODEL_NAME
    global PREFIX_FKX
    global PREFIX_FK

    _print_verbose("initial settings for " + MODEL_NAME, 1)
    if (MODEL_NAME == 'Mosko_Rigged'):
        PREFIX_FKX = 'FKX'
        PREFIX_FK = 'FK'
    elif (MODEL_NAME == "DeepSea_Rigged"):
        PREFIX_FKX = 'FKX'
        PREFIX_FK = 'FK'


################################################################################
##########          If you need any pre transform, fill it here
##########          Provided as an example (Might differ with models as shown)
################################################################################
def _fill_root_system():
    if (MODEL_NAME == 'Mosko_Rigged'):
        _print_verbose("Root system for " + MODEL_NAME, 1)
        all_maya_joints = pmc.ls(type="transform")
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
    elif (MODEL_NAME == 'DeepSea_Rigged'):
        _print_verbose("Root system for " + MODEL_NAME, 1)
        all_maya_joints = pmc.ls(type="transform")
        for maya_joint in all_maya_joints:
            if (maya_joint.name() == "FKOffsetRoot_M"):
                _print_verbose("we have our root pre transform", 1)
                ROOTS_SYSTEM[maya_joint.name()] = maya_joint
            elif (maya_joint.name() == "RootOffsetX_M"):
                _print_verbose("we have RootOffsetX_M", 1)
                ROOTS_SYSTEM[maya_joint.name()] = maya_joint


################################################################################
##########          Return the controller name for the associated joint_name
################################################################################
def _deepsea_controllers(joint_name):
    prefixed_name = PREFIX_FK + joint_name

    # except for RooX_M which we want as is with no prefix
    if joint_name == "RootX_M":
        prefixed_name = joint_name
        return prefixed_name

    # except for the joints we want to map directly on FKX joints
    names = [name for name in DEEPSEA_FKX_BIND if name == joint_name]
    if len(names) > 0:
        prefixed_name = PREFIX_FKX + joint_name

    return prefixed_name


################################################################################
################################################################################
def _compute_extra(joint_name):
    global JOINTS_BUFFER
    global JOINTS_ROTATE_AXIS_INV_BUFFER
    global JOINTS_INIT_ORIENT_INV_BUFFER

    #maya_joint = JOINTS_BUFFER[joint_name]

    # First compute X (= extra transformation)
    # X = P^-1 * G * L^-1
#    parent_joint = maya_joint.getParent()
 #   P_inv = parent_joint.getRotation(space='world', quaternion=True).inverse()

  #  G = maya_joint.getRotation(space='world', quaternion=True)

    X = pmc.datatypes.EulerRotation(0, 0, 0).asQuaternion()

    if (joint_name == 'ThumbFinger1_L'):
        print joint_name
        #all_maya_joints = pmc.ls(type="joint")
        #thumb_joints = [maya_joint for maya_joint in all_maya_joints if maya_joint.name() == 'ThumbFinger1_L']
        #thumb_joint = thumb_joints[0]
        #L = thumb_joint.getRotation(space='transform', quaternion=True)
        #vRO = maya_joint.getRotateAxis()
        #RO = pmc.datatypes.EulerRotation(vRO[0], vRO[1], vRO[2]).asQuaternion()
        #JO = maya_joint.getOrientation()

        try:
            thumb_joint = JOINTS_BUFFER[joint_name]
        except KeyError as e:
            _print_error("cannot find " + joint_name + " in buffers" + ": " + str(e))
            return X

        L = thumb_joint.getRotation(space='transform', quaternion=True)
        RO = JOINTS_ROTATE_AXIS_INV_BUFFER[joint_name]
        JO = JOINTS_INIT_ORIENT_INV_BUFFER[joint_name]

        L = RO * L * JO
        X = L

        M = X
        M_euler = M.asEulerRotation()
        print M_euler[0]*180/3.1415926535897932384626433832795
        print M_euler[1]*180/3.1415926535897932384626433832795
        print M_euler[2]*180/3.1415926535897932384626433832795

    return X


################################################################################
##########          return 3 euler angle from a quaternion
################################################################################
def quat_to_deg(quat):
    vec = quat.asEulerRotation()
    vec = vec * (180.0 / 3.1415926535897932384626433832795)
    return vec


################################################################################
##########          print a quaternion as 3 euler angles
################################################################################
def print_quat_deg(name, quat):
    vec = quat_to_deg(quat)
    print name + '= ' + str(vec[0]) + ' ' + str(vec[1]) + ' ' + str(vec[2])


################################################################################
##########          ...
################################################################################
def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False
    return True


################################################################################
##########          ...
################################################################################
def is_valid_ipv6_address(address):
    try:
        socket.inet_pton(socket.AF_INET6, address)
    except socket.error:  # not a valid address
        return False
    return True


################################################################################
##########          ...
################################################################################
