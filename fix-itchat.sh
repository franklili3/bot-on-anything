#!/bin/bash

# Define the file name and the line number
pack_dir="$(pip3 show itchat-uos | grep "Location" | awk '{print $2}')"
file_name="${pack_dir}/itchat/components/login.py"
line_number=59

# Define the line of code to be inserted
code="time.sleep(15)"
line_of_code="\ \ \ \ \ \ \ \ $code"

# Use the sed command to insert the line
sed -i "${line_number}i ${line_of_code}" "${file_name}"

# Define the start and end line numbers
start_line=50
end_line=70

# Use the sed command to print the desired lines
sed -n "${start_line},${end_line}p" "${file_name}"
