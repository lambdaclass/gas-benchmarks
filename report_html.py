import argparse
import json
import os
import re

import yaml
from bs4 import BeautifulSoup
import utils
import csv


def parse_test_title(full_title):
    """
    Parse long test titles like:
    'tests_benchmark_test_worst_compute.py__test_worst_modexp[fork_Prague-benchmark-blockchain_test_engine_x_from_state_test-mod_400_gas_exp_heavy]-gas-value'
    Into readable format and return both readable title and full title for alt text
    """
    if not full_title or len(full_title) < 50:
        return full_title, full_title
    
    parts = []
    
    # Extract test category from filename
    category_match = re.search(r'test_worst_([^\.]+)\.py', full_title)
    if category_match:
        category = category_match.group(1).replace('_', ' ').title()
        parts.append(category)
    
    # Extract test function name
    test_match = re.search(r'__test_worst_([^[]+)', full_title)
    if test_match:
        test_name = test_match.group(1).replace('_', ' ').title()
        parts.append(test_name)
    
    # Extract opcode information
    opcode_match = re.search(r'opcode_([A-Z0-9]+)', full_title)
    if opcode_match:
        parts.append(f"Op: {opcode_match.group(1)}")
    
    # Extract specific modexp parameters
    modexp_param_match = re.search(r'mod_([a-z0-9_]+)', full_title)
    if modexp_param_match:
        param = modexp_param_match.group(1).replace('_', ' ').title()
        parts.append(f"Mod: {param}")
    
    # Extract data sizes (improved pattern)
    size_matches = re.findall(r'(\d+(?:\.\d+)?[x]?\s*(?:KiB|MiB|bytes?)|(?:0\.\d+x\s*)?max code size|\d+\s+bytes)', full_title)
    if size_matches:
        parts.append(size_matches[0])
    
    # Extract key parameters for memory/access tests
    key_params = []
    
    # Memory expansion
    if 'big_memory_expansion_True' in full_title:
        key_params.append('Big Mem')
    elif 'big_memory_expansion_False' in full_title:
        key_params.append('No Big Mem')
    
    # Fixed parameters
    if 'fixed_src_dst_True' in full_title:
        key_params.append('Fixed Src/Dst')
    elif 'fixed_src_dst_False' in full_title:
        key_params.append('Var Src/Dst')
        
    if 'fixed_offset_True' in full_title:
        key_params.append('Fixed Offset')
    elif 'fixed_offset_False' in full_title:
        key_params.append('Var Offset')
    
    # Data types
    if 'non_zero_data_True' in full_title:
        key_params.append('Non-Zero Data')
    elif 'non_zero_data_False' in full_title:
        key_params.append('Zero Data')
        
    # Zero byte parameter
    if 'zero_byte_True' in full_title:
        key_params.append('Zero Byte')
    elif 'zero_byte_False' in full_title:
        key_params.append('Non-Zero Byte')
    
    # Case IDs for transfers
    case_match = re.search(r'case_id_([^-\]]+)', full_title)
    if case_match:
        case_id = case_match.group(1).replace('_', ' ').title()
        key_params.append(case_id)
    
    # Add key params if we have them and space
    if key_params and len(parts) < 4:
        parts.append(" | ".join(key_params[:2]))  # Limit to 2 key params
    
    # Extract fork (lower priority now)
    fork_match = re.search(r'fork_([^-]+)', full_title)
    if fork_match and len(parts) < 4:  # Only add if we have space
        parts.append(fork_match.group(1))
    
    # Extract memory size parameters
    mem_size_match = re.search(r'mem_size_(\d+)', full_title)
    if mem_size_match and len(parts) < 4:
        size = mem_size_match.group(1)
        if size == '0':
            key_params.append('Mem Size: 0')
        else:
            key_params.append(f'Mem Size: {size}')
    
    # Extract mod operation types with bits
    mod_op_match = re.search(r'op_(MOD|SMOD|ADDMOD|MULMOD)-mod_bits_(\d+)', full_title)
    if mod_op_match and len(parts) < 4:
        op_type = mod_op_match.group(1)
        bits = mod_op_match.group(2)
        parts.append(f"{op_type} {bits}b")
    
    # Extract BLS12/BN128 precompile types
    precompile_match = re.search(r'(bn128|bls12)_([a-z0-9_]+)', full_title)
    if precompile_match and len(parts) < 4:
        crypto_type = precompile_match.group(1).upper()
        operation = precompile_match.group(2).replace('_', ' ').title()
        if len(operation) < 15:  # Keep it short
            parts.append(f"{crypto_type}: {operation}")
    
    # Extract blobhash parameters
    if 'no blobs' in full_title and len(parts) < 4:
        key_params.append('No Blobs')
    elif 'one blob and accessed' in full_title and len(parts) < 4:
        key_params.append('One Blob')
    
    # Extract calldataload loop types
    if 'one-loop' in full_title and len(parts) < 4:
        key_params.append('One Loop')
    elif 'zero-loop' in full_title and len(parts) < 4:
        key_params.append('Zero Loop')
    
    # Extract return data styles
    if 'ReturnDataStyle.IDENTITY' in full_title and len(parts) < 4:
        key_params.append('Identity Style')
    elif 'ReturnDataStyle.RETURN' in full_title and len(parts) < 4:
        key_params.append('Return Style')
    
    # Extract call types
    if full_title.endswith('-call]-gas-value') and len(parts) < 4:
        key_params.append('Call')
    elif full_title.endswith('-transaction]-gas-value') and len(parts) < 4:
        key_params.append('Transaction')
    
    # Extract value parameters
    if 'from_origin_True' in full_title and 'non_zero_value_True' in full_title and len(parts) < 4:
        key_params.append('Origin + Value')
    elif 'from_origin_False' in full_title and 'non_zero_value_True' in full_title and len(parts) < 4:
        key_params.append('Non-Origin + Value')
    
    # Extract offset information for memory access
    offset_match = re.search(r'offset_(\d+)', full_title)
    if offset_match and len(parts) < 4:
        offset = offset_match.group(1)
        if offset == '0':
            key_params.append('Offset 0')
        elif offset == '1':
            key_params.append('Offset 1')
        elif offset == '31':
            key_params.append('Offset 31')
    
    # Extract returned size
    returned_size_match = re.search(r'returned_size_(\d+)', full_title)
    if returned_size_match and len(parts) < 4:
        size = returned_size_match.group(1)
        key_params.append(f'Ret Size: {size}')
    
    # Extract log operation types
    log_match = re.search(r'-(log\d+)', full_title)
    if log_match and len(parts) < 4:
        parts.append(log_match.group(1).upper())
    
    # Extract topic types  
    if 'non_zero_topic' in full_title and len(parts) < 4:
        key_params.append('Non-Zero Topic')
    elif 'zeros_topic' in full_title and len(parts) < 4:
        key_params.append('Zero Topic')
    
    # Create readable title
    if parts:
        readable_title = " | ".join(parts[:4])  # Limit to 4 parts
        # Limit total length
        if len(readable_title) > 90:
            readable_title = readable_title[:87] + "..."
    else:
        # Fallback: just clean up underscores and limit length
        readable_title = full_title.replace('_', ' ').replace('.py', '')
        if len(readable_title) > 60:
            readable_title = readable_title[:57] + "..."
    
    return readable_title, full_title


def get_html_report(client_results, clients, results_paths, test_cases, methods, gas_set, metadata, images):
    # Load the computer specs
    with open(os.path.join(results_paths, 'computer_specs.txt'), 'r') as file:
        text = file.read()
        computer_spec = text

    results_to_print = ('<!DOCTYPE html>' +
                        '<html lang="en">' +
                        '<head>' +
                        '    <meta charset=\"UTF-8\">' +
                        '    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">' +
                        '    <title>Benchmarking Report</title>' +
                        '    <style>' +
                        '        body {' +
                        '            font-family: Arial, sans-serif;' +
                        '        }' +
                        '        table {' +
                        # '            width: 100%;' +
                        '            border-collapse: collapse;' +
                        '            margin-bottom: 20px;' +
                        '        }' +
                        '        th, td {' +
                        '            border: 1px solid #ddd;' +
                        '            padding: 8px;' +
                        '            text-align: center;' +
                        '        }' +
                        '        th {' +
                        '            background-color: #f2f2f2;' +
                        # '            cursor: pointer;' +
                        '        }' +
                        '        .title {' +
                        '            text-align: left;' +
                        '        }' +
                        '        .preserve-newlines {' +
                        '            white-space: pre-wrap;' +
                        '        }' +
                        '    </style>' +
                        '</head>' +
                        '<body>'
                        '<h2>Computer Specs</h2>'
                        '<pre">' + computer_spec + '</pre>')
    csv_table = {}
    for client in clients:
        image_to_print = ''
        image_json = json.loads(images)
        if client in image_json:
            if image_json[client] != 'default' and image_json[client] != '':
                image_to_print = image_json[client]
        if image_to_print == '':
            with open('images.yaml', 'r') as f:
                el_images = yaml.safe_load(f)["images"]
            client_without_tag = client.split("_")[0]
            image_to_print = el_images[client_without_tag]
        results_to_print += f'<h1>{client.capitalize()} - {image_to_print} - Benchmarking Report</h1>' + '\n'
        results_to_print += f'<table id="table_{client}">'
        results_to_print += ('<thead>\n'
                             '<tr>\n'
                             f'<th class=\"title\" onclick="sortTable(0, \'table_{client}\', false)" style="cursor: pointer;">Title &uarr; &darr;</th>\n'
                             f'<th onclick="sortTable(1, \'table_{client}\', true)" style="cursor: pointer;">Max (MGas/s) &uarr; &darr;</th>\n'
                             f'<th onclick="sortTable(2, \'table_{client}\', true)" style="cursor: pointer;">p50 (MGas/s) &uarr; &darr;</th>\n'
                             f'<th onclick="sortTable(3, \'table_{client}\', true)" style="cursor: pointer;">p95 (MGas/s) &uarr; &darr;</th>\n'
                             f'<th onclick="sortTable(4, \'table_{client}\', true)" style="cursor: pointer;">p99 (MGas/s) &uarr; &darr;</th>\n'
                             f'<th onclick="sortTable(5, \'table_{client}\', true)" style="cursor: pointer;">Min (MGas/s) &uarr; &darr;</th>\n'
                             '<th>N</th>\n'
                             '<th class=\"title\">Description</th>\n'
                             '<th>Start Time</th>\n'
                             '</tr>\n'
                             '</thead>\n'
                             '<tbody>\n')
        gas_table_norm = utils.get_gas_table(client_results, client, test_cases, gas_set, methods[0], metadata)
        csv_table[client] = gas_table_norm
        for test_case, data in gas_table_norm.items():
            readable_title, full_title = parse_test_title(data[0])
            results_to_print += (f'<tr>\n<td class="title" title="{full_title}">{readable_title}</td>\n'
                                 f'<td>{data[2]}</td>\n'
                                 f'<td>{data[3]}</td>\n'
                                 f'<td>{data[4]}</td>\n'
                                 f'<td>{data[5]}</td>\n'
                                 f'<td>{data[1]}</td>\n'
                                 f'<td>{data[6]}</td>\n'
                                 f'<td style="text-align:left;" >{data[7]}</td>\n'
                                 f'<td>{data[8]}</td>\n</tr>\n')
        results_to_print += '\n'
        results_to_print += ('</tbody>\n'
                             '</table>\n')

    results_to_print += ('    <script>'
                         'var sortDirection = {};'
                         'function sortTable(n, table_name, nm) {'
                         '  var table = document.getElementById(table_name);'
                         '  var tbody = table.tBodies[0];'
                         '  var rows = Array.from(tbody.rows);'
                         '  '
                         '  var currentDir = sortDirection[table_name + "_" + n] || "asc";'
                         '  var newDir = currentDir === "asc" ? "desc" : "asc";'
                         '  sortDirection[table_name + "_" + n] = newDir;'
                         '  '
                         '  rows.sort(function(a, b) {'
                         '    var x = a.getElementsByTagName("TD")[n].innerHTML;'
                         '    var y = b.getElementsByTagName("TD")[n].innerHTML;'
                         '    '
                         '    var valX, valY;'
                         '    if (nm) {'
                         '      valX = parseFloat(x) || 0;'
                         '      valY = parseFloat(y) || 0;'
                         '    } else {'
                         '      valX = x.toLowerCase();'
                         '      valY = y.toLowerCase();'
                         '    }'
                         '    '
                         '    if (newDir === "asc") {'
                         '      return valX > valY ? 1 : valX < valY ? -1 : 0;'
                         '    } else {'
                         '      return valX < valY ? 1 : valX > valY ? -1 : 0;'
                         '    }'
                         '  });'
                         '  '
                         '  rows.forEach(function(row) {'
                         '    tbody.appendChild(row);'
                         '  });'
                         '}'
                         '</script>'
                         '</body>'
                         '</html>')

    soup = BeautifulSoup(results_to_print, 'lxml')
    formatted_html = soup.prettify()
    if not os.path.exists('reports'):
        os.mkdir('reports')
    with open(f'reports/index.html', 'w') as file:
        file.write(formatted_html)

    for client, gas_table in csv_table.items():
        with open(f'reports/output_{client}.csv', 'w', newline='') as csvfile:
            # Create a CSV writer object
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(
                ['Title', 'Max (MGas/s)', 'p50 (MGas/s)', 'p95 (MGas/s)', 'p99 (MGas/s)', 'Min (MGas/s)', 'N',
                 'Description', "Start Time"])
            for test_case, data in gas_table.items():
                csvwriter.writerow([data[0], data[2], data[3], data[4], data[5], data[1], data[6], data[7], data[8]])


def main():
    parser = argparse.ArgumentParser(description='Benchmark script')
    parser.add_argument('--resultsPath', type=str, help='Path to gather the results', default='results/results')
    parser.add_argument('--testsPath', type=str, help='results', default='tests/')
    parser.add_argument('--clients', type=str, help='Client we want to gather the metrics, if you want to compare, '
                                                    'split them by comma, ex: nethermind,geth',
                        default='nethermind,geth,reth,erigon,besu,nimbus,ethrex')
    parser.add_argument('--runs', type=int, help='Number of runs the program will process', default='8')
    parser.add_argument('--images', type=str, help='Image values per each client',
                        default='{"nethermind":"default","geth":"default","reth":"default","erigon":"default","besu":"default","nimbus":"default","ethrex":"default"}')

    # Parse command-line arguments
    args = parser.parse_args()

    # Get client name and test case folder from command-line arguments
    results_paths = args.resultsPath
    clients = args.clients
    tests_path = args.testsPath
    runs = args.runs
    images = args.images

    client_results = {}
    failed_tests = {}
    methods = ['engine_newPayloadV4']
    fields = 'max'

    test_cases = utils.get_test_cases(tests_path)
    for client in clients.split(','):
        client_results[client] = {}
        failed_tests[client] = {}
        for test_case_name, test_case_gas in test_cases.items():
            client_results[client][test_case_name] = {}
            failed_tests[client][test_case_name] = {}
            for gas in test_case_gas:
                client_results[client][test_case_name][gas] = {}
                failed_tests[client][test_case_name][gas] = {}
                for method in methods:
                    client_results[client][test_case_name][gas][method] = []
                    failed_tests[client][test_case_name][gas][method] = []
                    for run in range(1, runs + 1):
                        responses, results, timestamp = utils.extract_response_and_result(results_paths, client, test_case_name,
                                                                               gas, run, method, fields)
                        client_results[client][test_case_name][gas][method].append(results)
                        failed_tests[client][test_case_name][gas][method].append(not responses)
                        # print(test_case_name + " : " + str(timestamp))
                        if str(timestamp) != "0":
                            client_results[client][test_case_name]["timestamp"] = utils.convert_dotnet_ticks_to_utc(timestamp)
                        else:
                            if "timestamp" not in str(client_results[client][test_case_name]):
                                client_results[client][test_case_name]["timestamp"] = 0

    gas_set = set()
    for test_case_name, test_case_gas in test_cases.items():
        for gas in test_case_gas:
            if gas not in gas_set:
                gas_set.add(gas)

    if not os.path.exists(f'{results_paths}/reports'):
        os.makedirs(f'{results_paths}/reports')

    metadata = {}
    if os.path.exists(f'{tests_path}/metadata.json'):
        data = json.load(open(f'{tests_path}/metadata.json', 'r'))
        for item in data:
            metadata[item['Name']] = item

    # Create .csv with raw results per client
    for client in client_results:
        with open(f'reports/raw_results_{client}.csv', 'w', newline='') as csvfile:
            # Create a CSV writer object
            csvwriter = csv.writer(csvfile)
            rows = ['Test Case', 'Gas'] + [f'Run {i}' for i in range(1, runs + 1)] + ['Description']
            csvwriter.writerow(rows)
            for test_case_name, test_case_gas in test_cases.items():
                for gas in test_case_gas:
                    name = test_case_name
                    description = 'Description not found on metadata file'
                    if test_case_name in metadata:
                        name = metadata[test_case_name]['Title']
                        description = metadata[test_case_name]['Description']

                    rows = [name, gas] + client_results[client][test_case_name][gas][methods[0]] + [description]
                    csvwriter.writerow(rows)

    get_html_report(client_results, clients.split(','), results_paths, test_cases, methods, gas_set, metadata, images)

    print('Done!')


if __name__ == '__main__':
    main()
