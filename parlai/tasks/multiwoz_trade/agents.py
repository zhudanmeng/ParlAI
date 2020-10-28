#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from parlai.core.teachers import FixedDialogTeacher
from parlai.core.message import Message
from parlai.core.metrics import AverageMetric
from .build import build
import os
import json
import random


class MultiWozTradeTeacher(FixedDialogTeacher):
    """
    MultiWOZ 2.1 Teacher with TRADE preprocess
    Two main differences from multiwoz_v2.1:
    1. with TRADE preprocess, which would normalize and split data
    into "_train.json" "_val.json" and "_test.json"
    2. each turn is an individual episode, turn["context"] includes
    all the dialog history in previous turns.
    """
    def __init__(self, opt, shared=None):
        super().__init__(opt, shared)
        self.id = 'multiwoz_trade'
        opt['datafile'], data_dir = self._path(opt)
        self._setup_data(opt['datafile'], data_dir)
        self.reset()


    def _load_json(self, file_path):
        with open(file_path) as df:
            data = json.load(df)
        return data


    def _setup_data(self, data_path, jsons_path):
        # loading directly from test file or val file or train file
        if self.datatype.startswith('test'):
            test_path = data_path.replace(".json", "_test.json")
            test_data = self._load_json(test_path)
            self.messages = list(test_data.values())
        elif self.datatype.startswith('valid'):
            valid_path = data_path.replace(".json", "_valid.json")
            valid_data = self._load_json(valid_path)
            self.messages = list(valid_data.values())
        else:
            train_path = data_path.replace(".json", "_train.json")
            train_data = self._load_json(train_path)
            self.messages = list(train_data.values())
            random.shuffle(self.messages)


    def _path(self, opt):
        # set up path to data (specific to each dataset)
        opt['datapath'] = "/tmp/parlai_data"
        data_dir = os.path.join(opt['datapath'], 'multiwoz21_trade',
'MULTIWOZ2.1')
        data_path = os.path.join(data_dir, 'data_trade_reformat.json')

        # build the data if it does not exist
        build(opt)

        return data_path, data_dir


    def num_examples(self):
        # each turn be seen as a individual dialog
        return len(self.messages)


    def num_episodes(self):
        return len(self.messages)


    def get(self, episode_idx, entry_idx=0):
        entry = self.messages[episode_idx]['context']
        episode_done = True
        action = {
            'id': self.id,
            'text': entry,
            'episode_done': episode_done,
            'labels': [self.messages[episode_idx]['response']],
            'dial_id': self.messages[episode_idx]['dial_id'],
            'turn_num': self.messages[episode_idx]['turn_num'],
        }
        return action


class MultiWozTradeDSTTeacher(MultiWozTradeTeacher):
    """
    MultiWOZ2.1 Dialog State Tracking (DST) Teacher with TRADE preprocess,
    Each turn contains all the dialog history in the previous (turn["context"])
    and is expected to generate all previous dialog slots. Therefore, each turn
    is a individual episode.
    """
    def __init__(self, opt, shared=None):
        super().__init__(opt, shared)
        self.id = 'multiwoz_trade'
        self.reset()


    def _extract_slot_from_string(self, slots_string):
        """
        Either ground truth or generated result should be in the format:
        "dom slot_type slot_val, dom slot_type slot_val, ..., dom slot_type
slot_val,"
        and this function would reformat the string into list:
        ["dom--slot_type--slot_val", ... ]
        """
        domains    = ["attraction", "hotel", "hospital", "restaurant",
"police", "taxi", "train"]
        slots_list = []

        # split according to ","
        str_split = slots_string.strip().split(",")
        if str_split[-1] == "":
            str_split = str_split[:-1]
        str_split = [slot.strip() for slot in str_split]

        for slot_ in str_split:
            slot = slot_.split()
            if len(slot) > 2 and slot[0] in domains:
                domain = slot[0]
                if slot[1] == "book" and slot[2] in ["day", "time", "people",
"stay"]:
                    slot_type = slot[1]+" "+slot[2]
                    slot_val  = " ".join(slot[3:])
                else:
                    slot_type = slot[1]
                    slot_val  = " ".join(slot[2:])
                if not slot_val == 'dontcare':
                    slots_list.append(domain+"--"+slot_type+"--"+slot_val)
        return slots_list


    def custom_evaluation(self, teacher_action: Message, labels,
model_response: Message):
        """
        for dialog state tracking, we compute the joint goal accuracy, which is
        the percentage of the turns where the model correctly and precisely
        predicts all slots(domain, slot_type, slot_value).
        """
        resp = model_response.get('text')
        if not resp:
            return

        # extract ground truth from labels
        slots_truth = self._extract_slot_from_string(labels[0])

        # extract generated slots from model_response
        slots_pred = self._extract_slot_from_string(resp)

        self.metrics.add('joint goal acc', AverageMetric(set(slots_truth) ==
set(slots_pred)))


    def get(self, episode_idx, entry_idx=0):
        entry = self.messages[episode_idx]['context'] # includes all previous dialog history
        episode_done = True     # each turn is a individual episode
        action = {
            'id': self.id,
            'text': entry,
            'domain':self.messages[episode_idx]['domain'],
            'episode_done': episode_done,
            'labels': [self.messages[episode_idx]['slots']],
            'dial_id': self.messages[episode_idx]['dial_id'],
            'turn_num': self.messages[episode_idx]['turn_num'],
        }
        return action


class DefaultTeacher(MultiWozTradeDSTTeacher):
    pass
