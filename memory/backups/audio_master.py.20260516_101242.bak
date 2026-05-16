# JARVIS Audio Master - Soundscape Controller
import ctypes
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from comtypes import CLSCTX_ALL

class AudioMaster:
    @staticmethod
    def set_master_volume(level):
        """Sets global system volume (0 to 100)."""
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        # level is 0-100, needs to be normalized to 0.0-1.0
        normalized_level = max(0.0, min(1.0, level / 100.0))
        volume.SetMasterVolumeLevelScalar(normalized_level, None)
        return f"Master volume set to {level}%, sir."

    @staticmethod
    def set_app_volume(app_name, level):
        """Sets volume for a specific application."""
        sessions = AudioUtilities.GetAllSessions()
        normalized_level = max(0.0, min(1.0, level / 100.0))
        found = False
        
        for session in sessions:
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            if session.Process and session.Process.name().lower() == app_name.lower():
                volume.SetMasterVolume(normalized_level, None)
                found = True
        
        if found:
            return f"Volume for {app_name} set to {level}%, sir."
        return f"I couldn't find an active audio session for '{app_name}', sir."

    @staticmethod
    def mute_all(status=True):
        """Mutes or unmutes all audio."""
        devices = AudioUtilities.GetSpeakers()
        from pycaw.pycaw import IAudioEndpointVolume
        from ctypes import cast, POINTER
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(1 if status else 0, None)
        return "System muted, sir." if status else "System unmuted, sir."

def audio_master(parameters, player=None):
    action = parameters.get("action", "set_volume").lower()
    level = parameters.get("level", 50)
    app = parameters.get("app_name", None)
    
    master = AudioMaster()
    
    if action == "mute":
        return master.mute_all(True)
    elif action == "unmute":
        return master.mute_all(False)
    elif action == "app_volume" and app:
        return master.set_app_volume(app, level)
    else:
        return master.set_master_volume(level)
