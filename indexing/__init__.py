import pandas as pd
import os

class IndexParameter:
    def __init__(self):
        pass


class Index:
    def __init__(self, name: str, parameters: list[str], ):
        self.name = name
        self.dict_data = {}
        for parameter in parameters:
            self.dict_data[parameter] = []
        print(self.dict_data)





class IndexSystem:
    def __init__(self, index_folder_filepath):
        self.indexes = {}
        self.index_folder_filepath = index_folder_filepath

    def __load_inital_indexes(self):
        files = os.listdir(self.index_folder_filepath)
        for file in files:
            if file.endswith(".index"):
                df = pd.read_pickle(file)

    def create_index(self, name, parameters: list[str]):
        index = Index(name=name, parameters=parameters)
        self.indexes[name] = index
        return index
