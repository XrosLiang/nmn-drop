import logging
from typing import List, Iterable
import random

import torch
from torch.utils import data

from allennlp.common.checks import ConfigurationError
from allennlp.common.util import lazy_groups_of
from allennlp.data.instance import Instance
from allennlp.data.samplers import BatchSampler
from allennlp.data.samplers import Sampler
# from torch.utils.data import Sampler
from allennlp.data.dataloader import DataLoader
from allennlp.data.dataset_readers import DatasetReader
from allennlp.training.trainer import GradientDescentTrainer
import allennlp.commands.train
logger = logging.getLogger(__name__)


@Sampler.register("curriculum")
class CurriculumSampler(data.Sampler):
    r"""Samples elements randomly. If without replacement, then sample from a shuffled dataset.
    If with replacement, then user can specify :attr:`num_samples` to draw.

    Arguments:
        data_source (Dataset): dataset to sample from
        replacement (bool): samples are drawn with replacement if ``True``, default=``False``
        num_samples (int): number of samples to draw, default=`len(dataset)`. This argument
            is supposed to be specified only when `replacement` is ``True``.
    """

    def __init__(self, data_source, num_samples=None, supervised_field: str = "strongly_supervised",
                 supervised_epochs: int = 0):
        # super().__init__(data_source)
        self.data_source = data_source
        self._num_samples = num_samples
        self._supervised_field = supervised_field
        self._supervised_epochs = supervised_epochs
        self.epoch_num = 0

        if isinstance(data_source, data.IterableDataset):
            raise ValueError("curriculum sampler only works with AllennlpDataset, i.e. non-lazy reading.")

        if not isinstance(self.num_samples, int) or self.num_samples <= 0:
            raise ValueError("num_samples should be a positive integer "
                             "value, but got num_samples={}".format(self.num_samples))

    @property
    def num_samples(self):
        # dataset size might change at runtime
        if self._num_samples is None:
            return len(self.data_source)
        return self._num_samples

    def __iter__(self):
        logger.info("iterator called; epoch-num: {}".format(self.epoch_num))
        if self.epoch_num < self._supervised_epochs:
            supervised_idxs = []
            for idx, instance in enumerate(self.data_source):
                instance: Instance = instance
                if self._supervised_field in instance.fields and instance.fields[self._supervised_field].metadata is True:
                    supervised_idxs.append(idx)
            random.shuffle(supervised_idxs)
        else:
            n = len(self.data_source)
            supervised_idxs = torch.randperm(n).tolist()

        logger.info("num instances: {}".format(len(supervised_idxs)))
        self.epoch_num += 1
        return iter(supervised_idxs)

    def __len__(self):
        return self.num_samples


# @BatchSampler.register("bucket")
# class BucketBatchSampler(BatchSampler):
#     """
#     An sampler which by default, argsorts batches with respect to the maximum input lengths `per
#     batch`. You can provide a list of field names and padding keys (or pass none, in which case they
#     will be inferred) which the dataset will be sorted by before doing this batching, causing inputs
#     with similar length to be batched together, making computation more efficient (as less time is
#     wasted on padded elements of the batch).
#
#     # Parameters
#
#     data_source: `data.Dataset`, required,
#         The pytorch `Dataset` of allennlp Instances to bucket.
#
#     batch_size : `int`, required.
#         The size of each batch of instances yielded when calling the dataloader.
#
#     sorting_keys : `List[str]`, optional
#         To bucket inputs into batches, we want to group the instances by padding length, so that we
#         minimize the amount of padding necessary per batch. In order to do this, we need to know
#         which fields need what type of padding, and in what order.
#
#         Specifying the right keys for this is a bit cryptic, so if this is not given we try to
#         auto-detect the right keys by iterating through a few instances upfront, reading all of the
#         padding keys and seeing which one has the longest length.  We use that one for padding.
#         This should give reasonable results in most cases. Some cases where it might not be the
#         right thing to do are when you have a `ListField[TextField]`, or when you have a really
#         long, constant length `ArrayField`.
#
#         When you need to specify this yourself, you can create an instance from your dataset and
#         call `Instance.get_padding_lengths()` to see a list of all keys used in your data.  You
#         should give one or more of those as the sorting keys here.
#
#     padding_noise : `float`, optional (default=.1)
#         When sorting by padding length, we add a bit of noise to the lengths, so that the sorting
#         isn't deterministic.  This parameter determines how much noise we add, as a percentage of
#         the actual padding value for each instance.
#
#     drop_last : `bool`, (default = False)
#         If `True`, the sampler will drop the last batch if
#         its size would be less than batch_size`.
#
#     """
#
#     def __init__(
#         self,
#         data_source: data.Dataset,
#         batch_size: int,
#         sorting_keys: List[str] = None,
#         padding_noise: float = 0.1,
#         drop_last: bool = False,
#     ):
#
#         self.vocab = data_source.vocab
#         self.sorting_keys = sorting_keys
#         self.padding_noise = padding_noise
#         self.batch_size = batch_size
#         self.data_source = data_source
#         self.drop_last = drop_last
#
#     def _argsort_by_padding(self, instances: Iterable[Instance]) -> List[int]:
#         """
#         Argsorts the instances by their padding lengths, using the keys in
#         `sorting_keys` (in the order in which they are provided). `sorting_keys`
#         is a list of `(field_name, padding_key)` tuples.
#         """
#         if not self.sorting_keys:
#             logger.info("No sorting keys given; trying to guess a good one")
#             self._guess_sorting_keys(instances)
#             logger.info(f"Using {self.sorting_keys} as the sorting keys")
#         instances_with_lengths = []
#         for instance in instances:
#             # Make sure instance is indexed before calling .get_padding
#             lengths = []
#             for field_name in self.sorting_keys:
#                 if field_name not in instance.fields:
#                     raise ConfigurationError(
#                         f'Sorting key "{field_name}" is not a field in instance. '
#                         f"Available fields/keys are {list(instance.fields.keys())}."
#                     )
#                 lengths.append(
#                     add_noise_to_value(len(instance.fields[field_name]), self.padding_noise)
#                 )
#             instances_with_lengths.append((lengths, instance))
#         with_indices = [(x, i) for i, x in enumerate(instances_with_lengths)]
#         with_indices.sort(key=lambda x: x[0][0])
#         return [instance_with_index[-1] for instance_with_index in with_indices]
#
#     def __iter__(self) -> Iterable[List[int]]:
#
#         indices = self._argsort_by_padding(self.data_source)
#         batches = []
#         for group in lazy_groups_of(indices, self.batch_size):
#             batch_indices = list(group)
#             if self.drop_last and len(batch_indices) < self.batch_size:
#                 continue
#             batches.append(batch_indices)
#         random.shuffle(batches)
#         for batch in batches:
#             yield batch
#
#     def _guess_sorting_keys(self, instances: Iterable[Instance], num_instances: int = 10) -> None:
#         """
#         Use `num_instances` instances from the dataset to infer the keys used
#         for sorting the dataset for bucketing.
#
#         # Parameters
#
#         instances : `Iterable[Instance]`, required.
#             The dataset to guess sorting keys for.
#         num_instances : `int`, optional (default = 10)
#             The number of instances to use to guess sorting keys. Typically
#             the default value is completely sufficient, but if your instances
#             are not homogeneous, you might need more.
#         """
#         max_length = 0.0
#         longest_field: str = None
#         for i, instance in enumerate(instances):
#             instance.index_fields(self.vocab)
#             for field_name, field in instance.fields.items():
#                 length = len(field)
#                 if length > max_length:
#                     max_length = length
#                     longest_field = field_name
#             if i > num_instances:
#                 # Only use num_instances instances to guess the sorting keys.
#                 break
#
#         if not longest_field:
#             # This shouldn't ever happen (you basically have to have an empty instance list), but
#             # just in case...
#             raise AssertionError(
#                 "Found no field that needed padding; we are surprised you got this error, please "
#                 "open an issue on github"
#             )
#         self.sorting_keys = [longest_field]
#
#     def __len__(self):
#         batch_count_float = len(self.data_source) / self.batch_size
#         if self.drop_last:
#             return math.floor(batch_count_float)
#         else:
#             return math.ceil(batch_count_float)