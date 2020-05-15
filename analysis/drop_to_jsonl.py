import argparse
import itertools
from semqa.utils.qdmr_utils import read_drop_dataset, node_from_dict, nested_expression_to_lisp, write_jsonl
from datasets.drop import constants
from semqa.domain_languages.drop_language_v2 import Date


def year_diffs(passage_date_objs):
    year_differences = []
    for (date1, date2) in itertools.product(passage_date_objs, repeat=2):
        year_diff = date1.year_diff(date2)
        if year_diff >= 0:
            if year_diff not in year_differences:
                year_differences.append(year_diff)

    return sorted(year_differences)


def get_json_dicts(drop_dataset):
    output_json_dicts = []

    for passage_id, passage_info in drop_dataset.items():
        passage = passage_info[constants.passage]
        passage_number_values = passage_info[constants.passage_num_normalized_values]
        passage_date_values = passage_info[constants.passage_date_normalized_values]
        passage_date_objs = [Date(day=d, month=m, year=y) for (d, m, y) in passage_date_values]
        year_differences = year_diffs(passage_date_objs)

        for qa in passage_info[constants.qa_pairs]:
            query_id = qa[constants.query_id]
            question = qa[constants.question]
            answer_annotation = qa[constants.answer]
            program_supervision = qa.get(constants.program_supervision, None)
            answer_passage_spans = qa[constants.answer_passage_spans]
            if program_supervision:
                nested_expr = node_from_dict(program_supervision).get_nested_expression_with_strings()
            else:
                nested_expr = []

            output_dict = {
                "question": question,
                "passage": passage,
                "query_id": query_id,
                "nested_expr": nested_expr,
                "answer_annotation": answer_annotation,
                "answer_passage_spans": answer_passage_spans,
                "passage_number_values": passage_number_values,
                "passage_date_values": passage_date_values,
                "year_differences": year_differences,
            }
            output_json_dicts.append(output_dict)

    return output_json_dicts


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop_json")
    parser.add_argument("--output_jsonl")
    args = parser.parse_args()

    drop_dataset = read_drop_dataset(args.drop_json)
    json_dicts = get_json_dicts(drop_dataset)

    write_jsonl(output_jsonl=args.output_jsonl, output_json_dicts=json_dicts)





