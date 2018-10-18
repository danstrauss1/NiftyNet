import numpy as np
import random
import pandas as pd
import tensorflow as tf
from tensorflow.python.data.util import nest

from niftynet.layer.base_layer import Layer
from niftynet.io.image_reader import param_to_dict
from niftynet.io.image_sets_partitioner import ImageSetsPartitioner

class CSVReader(Layer):
    
    def __init__(self, names=None):
        self.names = names
        self._paths = None
        self._labels = None
        self._df = None
        self.label_names = None
        self.dims = None

        super(CSVReader, self).__init__(name='csv_reader')
    
    def initialise(self, data_param, task_param=None, file_list=None):
        """
        this function takes in a data_param specifying the name of the source and the location of
        the csv data. Three input modes are supported:
        - 'label' - expects a csv with header subject_id,label.
        - 'features' - expects a csv with header subject_id,<name of feature 1>,<name of feature 2>
        e.g.::

             data_param = {'label': {'csv_data_file': 'path/to/some_data.csv', 'to_ohe': False}}
             
        :param data_param: dictionary of input sections
        :param task_param: Namespace object
        :param file_list: a dataframe generated by ImagePartitioner
            for cross validation, so
            that the reader only loads files in training/inference phases.

        
        """
        assert self.names is not None
        data_param = param_to_dict(data_param)
        if not task_param:
            task_param = {mod: (mod,) for mod in list(data_param)}
        try:
            if not isinstance(task_param, dict):
                task_param = vars(task_param)
        except ValueError:
            tf.logging.fatal(
                "To concatenate multiple input data arrays,\n"
                "task_param should be a dictionary in the form:\n"
                "{'new_modality_name': ['modality_1', 'modality_2',...]}.")
            raise
        self.task_param = task_param
        valid_names = [name for name in self.names if self.task_param.get(name, None)]
        if not valid_names:
            tf.logging.fatal("CSVReader requires task input keywords %s, but "
                             "not exist in the config file.\n"
                             "Available task keywords: %s",
                             self.names, list(self.task_param))
            raise ValueError
        self.names = valid_names
        self.data_param = data_param
        self._dims = None
        self._indexable_output = {}
        self.file_list = file_list
        self.subject_ids = self.file_list['subject_id'].values

        self._input_sources = dict((name, self.task_param.get(name)) for name in self.names)
        self.df_by_task = {}
        self.dims_by_task = {}

        for name in valid_names:
            df, _indexable_output, _dims = self._parse_csv(
                path_to_csv=data_param[name].get('csv_data_file', None),
                to_ohe=data_param[name].get('to_ohe', False)
            )
            self.df_by_task[name] = df
            self.dims_by_task[name] = _dims
            self._indexable_output[name] = _indexable_output
        # Converts Dictionary of Lists to List of Dictionaries
        self._indexable_output = pd.DataFrame(self._indexable_output).to_dict('records')
        assert file_list is not None
        return self
    
    def _parse_csv(self, path_to_csv, to_ohe):
        tf.logging.warning('This method will read your entire csv into memory')
        df = pd.read_csv(path_to_csv, index_col=0, header=None)
        if set(df.index) != set(self.subject_ids):
            print(set(self.subject_ids) - set(df.index))
            tf.logging.fatal('csv file provided at: {} does not have all the subject_ids'.format(path_to_csv))
            raise Exception
        if to_ohe and len(df.columns)==1:
            _dims = len(list(df[1].unique()))
            _indexable_output = self.to_ohe(df[1].values, _dims)
            return df, _indexable_output, _dims
        elif not to_ohe and len(df.columns==1):
            _dims = 1
            _indexable_output = self.to_categorical(df[1].values, df[1].unique())
            return df, _indexable_output, _dims
        elif not to_ohe:
            _dims = len(df.columns)
            _indexable_output = list(df.values)
            return df, _indexable_output, _dims
        else:
            tf.logging.fatal('Unrecognised input format for {}'.format(path_to_csv))

    @staticmethod
    def to_ohe(labels, _dims):
        label_names = list(set(labels))
        ohe = [np.eye(_dims)[label_names.index(label)].astype(np.float32) for label in labels]
        return ohe

    @staticmethod
    def to_categorical(labels, label_names):
        return [np.array(list(label_names).index(label)).astype(np.float32) for label in labels]

    def layer_op(self, idx=None, subject_id=None, ):
        if idx is None and subject_id is not None:
            #  Take the list of idx corresponding to subject id and randomly
            # sample from there
            relevant_indices = self._df.loc[subject_id]
            idx = random.choice(relevant_indices)
        elif idx is None:
            idx = np.random.randint(len(self.num_rows))
        if self._indexable_output is not None:
            output_dict = {k: self.apply_niftynet_format_to_data(v) for k, v\
                           in self._indexable_output[idx].items()}
            return idx, output_dict, None
        else:
            raise Exception('Invalid mode')
    
    @property
    def shapes(self):
        """
        :return: dict of label shape and label location shape
        """
        self._shapes = {}
        for name in self.names:
            self._shapes.update({name: (1, self.dims_by_task[name], 1, 1, 1, 1),
                        name + '_location': (1, 7)})        
        return self._shapes
    
    @property
    def tf_dtypes(self):
        """
        Infer input data dtypes in TF
        """
        self._dtypes = {}
        for name in self.names:
            self._dtypes.update({name: tf.float32,
                        name + '_location': tf.int32})
        return self._dtypes
    
    @property
    def tf_shapes(self):
        """
        :return: a dictionary of sampler output tensor shapes
        """
        output_shapes = nest.map_structure_up_to(
            self.tf_dtypes, tf.TensorShape, self.shapes)
        return output_shapes
<<<<<<< HEAD
=======
    
    @staticmethod
    def apply_niftynet_format_to_data(data):
        while len(data.shape) < 5:
            data = np.expand_dims(data, -1)
        return np.expand_dims(data, 0)
>>>>>>> Introduced support for multiple sources in a single CSV Reader
