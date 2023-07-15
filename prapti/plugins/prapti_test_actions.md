%plugins.load prapti.test.actions

% temperature = 0.2
% model = "gpt-3.5-turbo"
//% model = "gpt-3.5-turbo-0301"
//% model = "gpt-3.5-turbo-0613"
//% model = "gpt-4"

### @system:

You are a helpful, supportive and familiar assistant.

### @user:

% test.test
% !test.test foo bar baz 1
%! test.test foo bar baz 2
% ! test.test foo bar baz 3

% teest.test

The following is ambiguous:
% test

%!plugins.list
