"""A settings editor can keep a draft without overwriting unrelated changes."""
from copy import deepcopy


class SettingsDraft:
    def __init__(self,values):
        self.reset(values)

    def reset(self,values):
        self.baseline=deepcopy(values);self.values=deepcopy(values);self.conflicts=set()

    @property
    def dirty(self):
        return {key for key,value in self.values.items() if value!=self.baseline.get(key)}

    def set(self,key,value):
        self.values[key]=deepcopy(value)
        # A new edit after an external change is an explicit local choice.
        self.conflicts.discard(key)

    def rebase(self,values):
        dirty=self.dirty
        for key,value in values.items():
            if key not in self.values:continue
            if key not in dirty or value==self.values[key]:
                self.values[key]=deepcopy(value);self.conflicts.discard(key)
            elif value!=self.baseline.get(key):self.conflicts.add(key)
            self.baseline[key]=deepcopy(value)
        self.conflicts.intersection_update(self.dirty)

    def changes(self):
        return {key:deepcopy(self.values[key]) for key in self.dirty}
