# JARVIS Audio Master - Soundscape Controller
# ============================================================
# CRITICAL: DO NOT MODIFY _get_volume_interface()
# AudioUtilities.GetSpeakers() returns a pycaw AudioDevice
# object which wraps the COM interface. Use .EndpointVolume
# directly. DO NOT call .Activate() - it does not exist.
# ============================================================
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

def _get_volume_interface():
    """Get Windows master volume interface. Uses EndpointVolume property."""
    return AudioUtilities.GetSpeakers().EndpointVolume

class AudioMaster:
    @staticmethod
    def set_master_volume(level):
        volume = _get_volume_interface()
        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100.0)), None)
        return f"Master volume set to {level}%, sir."

    @staticmethod
    def get_master_volume():
        volume = _get_volume_interface()
        return f"Current volume is at {round(volume.GetMasterVolumeLevelScalar() * 100)}%, sir."

    @staticmethod
    def volume_up(amount=10):
        volume = _get_volume_interface()
        new = min(1.0, volume.GetMasterVolumeLevelScalar() + amount / 100.0)
        volume.SetMasterVolumeLevelScalar(new, None)
        return f"Volume increased to {round(new * 100)}%, sir."

    @staticmethod
    def volume_down(amount=10):
        volume = _get_volume_interface()
        new = max(0.0, volume.GetMasterVolumeLevelScalar() - amount / 100.0)
        volume.SetMasterVolumeLevelScalar(new, None)
        return f"Volume decreased to {round(new * 100)}%, sir."

    @staticmethod
    def mute_all(status=True):
        _get_volume_interface().SetMute(1 if status else 0, None)
        return "System muted, sir." if status else "System unmuted, sir."

    @staticmethod
    def set_app_volume(app_name, level):
        normalized = max(0.0, min(1.0, level / 100.0))
        for session in AudioUtilities.GetAllSessions():
            if session.Process and session.Process.name().lower() == app_name.lower():
                vol = session._ctl.QueryInterface(ISimpleAudioVolume)
                vol.SetMasterVolume(normalized, None)
                return f"Volume for {app_name} set to {level}%, sir."
        return f"No active audio session for '{app_name}', sir."

def audio_master(parameters, player=None):
    action = parameters.get("action", "set_volume").lower()
    level  = int(parameters.get("level", 50))
    amount = int(parameters.get("amount", 10))
    app    = parameters.get("app_name", None)

    master = AudioMaster()
    if action == "mute":           return master.mute_all(True)
    elif action == "unmute":       return master.mute_all(False)
    elif action == "volume_up":    return master.volume_up(amount)
    elif action == "volume_down":  return master.volume_down(amount)
    elif action == "get_volume":   return master.get_master_volume()
    elif action == "app_volume" and app: return master.set_app_volume(app, level)
    else:                          return master.set_master_volume(level)