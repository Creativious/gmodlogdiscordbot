import time
import os
import json


class CacheType:
    Additive = "Additive" # Each bit of information has its own delay for when it's wiped
    OneTime = "One Time" # All information gets cleanly wiped every time the delay passes

class Cache:
    def __init__(self, filename: str, cacheType, delay: int):
        self.filename = filename
        self.type = cacheType
        self.createdAt = round(time.time())
        self.delay = delay
        self.cache_dict = {
            "cache_type": str(cacheType),
            "special_entries": {}
        }
        if cacheType == CacheType.Additive:
            self.cache_dict["entries"] = {} # Contains the data
            self.cache_dict["timed_entries"] = {} # Contains the time relative data

        elif cacheType == CacheType.OneTime:
            self.cache_dict["creation_time"] = self.createdAt
            self.cache_dict["entries"] = {}
        else:
            raise "Not a valid CacheType"
        if not os.path.isfile(self.filename):
            self.saveCache()
        else:
            self.loadCache()
            if cacheType == CacheType.OneTime:
                self.createdAt = self.cache_dict["creation_time"]

    def check_if_delay_passed(self, entry: str = None):
        """Returns true if the delay is passed
        Returns false if the delay hasn't passed yet"""
        if self.type == CacheType.OneTime:
            if int(self.cache_dict["creation_time"]) + self.delay < round(time.time()):
                return True
            else:
                return False
        elif self.type == CacheType.Additive:
            if entry is None:
                raise "Provide an entry when using CacheType.Additive"
            else:
                if int(self.cache_dict["timed_entries"][entry]) + self.delay < round(time.time()):
                    return True
                else:
                    return False
        else:
            raise "Not a valid CacheType"

    def saveCache(self):
        with open(self.filename, "w+") as f:
            f.write(json.dumps(self.cache_dict))

    def loadCache(self):
        with open(self.filename, "r") as f:
            self.cache_dict = json.loads(f.read())
        return self.cache_dict

    def get_data(self):
        return self.cache_dict["entries"]

    def new_entry(self, name: str, data):
        if self.type == CacheType.OneTime:
            self.cache_dict["entries"][name] = data
        elif self.type == CacheType.Additive:
            self.cache_dict["entries"][name] = data
            self.cache_dict["timed_entries"][name] = round(time.time())
        else:
            raise "Not a valid CacheType"

    def delete_entry(self, name: str):
        self.cache_dict["entries"].pop(name)
        if self.type == CacheType.Additive:
            self.cache_dict["timed_entries"].pop(name)

    def wipe_all_entries(self):
        self.cache_dict["entries"] = {}
        if self.type == CacheType.Additive:
            self.cache_dict["timed_entries"] = {}

    def reset_created_time(self, entry: str = None):
        if self.type == CacheType.OneTime:
            newTime = round(time.time())
            self.createdAt = newTime
            self.cache_dict["created_at"] = newTime
        elif self.type == CacheType.Additive:
            if entry is None:
                raise "Provide an entry when using CacheType.Additive"
            else:
               self.cache_dict["timed_entries"][entry] = round(time.time())
        else:
            raise "Not a valid CacheType"

    def addSpecialEntry(self, name: str, data):
        self.cache_dict["special_entries"][name] = data

    def deleteSpecialEntry(self, name: str, data):
        self.cache_dict["special_entries"].pop(name)

    def getSpecialEntry(self, name: str):
        return self.cache_dict['special_entries'][name]

    def edit_entry(self, name: str, data):
        self.new_entry(name, data)

    def get_entry(self, name: str):
        return self.cache_dict["entries"][name]

    def __del__(self):
        self.saveCache()
class CacheSystem:
    """
    :parameter delay: int | The delay until the cache is destroyed or overwritten
    :parameter cacheFolder: str | Filepath of the folder where caches are to be stored
    """
    def __init__(self, delay: int, cacheFolder: str):
        self.delay = delay # Delay until the cache is destroyed
        self.caches = {}
        self.__cacheFirstTimes = {}
        if not os.path.exists(cacheFolder):
            raise "Folder doesn't exist [Caching]"
        self.cacheFolder = cacheFolder
        self.loadAllCaches()
    def loadAllCaches(self):
        files = os.listdir(self.cacheFolder)
        for file in files:
            if file.endswith(".json"):
                with open(os.path.join(self.cacheFolder, file), 'r') as f:
                    data = json.loads(f.read())
                self.createCache(file[:-5], data["cache_type"])
    def createCache(self, name: str, cacheType):
        if name in self.caches:
            return self.getCache(name)
        else:
            self.caches[str(name)] = Cache(os.path.join(self.cacheFolder, name + ".json"), cacheType=cacheType, delay=self.delay)
            self.__cacheFirstTimes[str(name)] = False
            return self.caches[str(name)]
    def updateCache(self, name: str, cache: Cache):
        cache.saveCache()
        self.caches[str(name)] = cache
    def getCache(self, name: str):
        return self.caches[str(name)]
    def deleteCache(self, name: str):
        self.caches.pop(str(name))
    def checkIfFirstTime(self, name: str):
        return self.__cacheFirstTimes[str(name)]
    def firstTimeComplete(self, name: str):
        self.__cacheFirstTimes[str(name)] = True


    def __del__(self):
        for cache in self.caches:
            self.caches[cache].saveCache()
