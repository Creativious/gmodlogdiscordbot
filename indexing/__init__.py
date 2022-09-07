import pandas as pd
import os
import pickle

class IndexParameter:
    def __init__(self):
        pass


class Index:
    def __init__(self, name: str, parameters: list[str], primary_index = False):
        self.name = name
        dict_data = {}
        for parameter in parameters:
            dict_data[parameter] = []
        self.df = pd.DataFrame(dict_data)
        del dict_data # Removing from memory
        if primary_index: # Primary index for information, could be a log ID or a steamid64 or anything depending on the type of index
            self.df.set_index([str(primary_index)])








class IndexSystem:
    def __init__(self, index_folder_filepath):
        self.indexes = {}
        self.index_folder_filepath = index_folder_filepath
        self.__load_inital_indexes()

    def __load_inital_indexes(self):
        files = os.listdir(self.index_folder_filepath)
        for file in files:
            if file.endswith(".index"):
                with open(os.path.join(self.index_folder_filepath, file), 'rb') as f:
                    index = pickle.load(f)
                    self.indexes[index.name] = index
                    print(index.name)

    def create_index(self, name, parameters: list[str], primary_index = False):
        if name in self.indexes:
            return self.indexes[name]
        else:
            self.__create_index(name, parameters, primary_index)

    def __create_index(self, name, parameters: list[str], primary_index = False):
        index = Index(name=name, parameters=parameters, primary_index=primary_index)
        self.indexes[name] = index
        self.__save_index(name)
        return index
    def __save_index(self, name):
        with open(f"{os.path.join(self.index_folder_filepath, name + '.index')} ", 'wb') as f:
            pickle.dump(self.indexes[name], f)
    def __load_index(self, name):
        with open(f"{os.path.join(self.index_folder_filepath, name + '.index')} ", 'rb') as f:
            index = pickle.load(f)
        self.indexes[name] = index
        return index
