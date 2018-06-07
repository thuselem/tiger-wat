import  os
import sys
import time
cwd = os.getcwd()
sys.path.append(os.path.join(cwd, "tiger-rpython"))

from src.parser import *


def die(err, outpath):
    err_message = 'Compilation error: ' + err
    print(err_message)
    outfile = open(outpath + '.err', 'w')
    outfile.write(err_message)
    outfile.close()
    sys.exit()

def set_int_return(env):
    env['return_type'] = 'i32'
    return env


# Variables

def variable_declaration(var, env):
    """Declare a variable
    Check if variable already declared and replace it if so.
    Otherwise, determine the type and assign it the next index as a label.
    Add to environment and generate stack code.
    """
    locals = [l[0] for l in env['locals']]
    if var.type is None and var.exp.__class__ is IntegerValue:
        type_ = 'i32'
    # elif var.type is None and var.exp.__class__ is StringValue:
        # type_ = 'string'
    elif var.type.name == 'int':
        type_ = 'i32'
    else:
        type_ = 'string'
    index = len(env['locals'])
    env['locals'].append( (var.name, type_) )
    set_local = ['set_local $' + str(index)]

    expr = comp(var.exp, env)[0]
    env['return_type'] = None

    return (expr + set_local, env)


def assign(assn, env):
    """Assign a local
    More needed to handle strings.
    """
    locals = [l[0] for l in env['locals']]
    if locals and assn.lvalue.name in locals:
        label = locals.index(assn.lvalue.name)

        expr = comp(assn.expression, env)[0]
        env['return_type'] = None

        return (expr + ['set_local $' + str(label)], env)
    else:
       die('variable ' + assn.lvalue.name + ' is not declared', env['outpath'])


def lvalue(lval, env):
    """Get value for an lval"""
    locals = [l[0] for l in env['locals']]
    if locals and lval.name in locals:
        labels = [i for i, x in enumerate(locals) if x == lval.name]
        label = labels[-1]
        type_ = env['locals'][label][1]
        env['return_type'] = type_
        return (['get_local $' + str(label)], env)
    else:
       print('here')
       die('variable ' + lval.name + ' is not declared', env['outpath'])


# Types

def type_id(typeid, env):
    """Retrieve type from TypeId node
    Strings will need to be handled here as well
    """
    if typeid.name == 'int':
        return ('i32', env)
    else:
        return ('', env)


# Functions

def function_declaration(func, env):
    """Declare a function
    Build up list of params as a list of tuples with name and type and return_type as a string
    Add function to environment.
    Generate stack code for function and append it to function declarations.
    Does not add stack code to main, so returns an empty list.
    """
    params = []
    for i in range(0, len(func.parameters)):
        params.append( (func.parameters[i].name, comp(func.parameters[i].type, env)[0]) )
    return_type = comp(func.return_type, env)[0]

    env['funcs'][func.name] = { 'params': params, 'return_type': return_type }

    param_string = ''
    for i in range(0, len(params)):
        param_string += '(param $' + str(i) + ' ' + params[i][1] + ') '

    if return_type:
        result_string = '(result ' + return_type + ')\n    '
        return_string = '\n    return'
    else:
        result_string = ''
        return_string = ''

    body_env = { 'locals': params, 'funcs': env['funcs'] }
    # body_env = { 'locals': env['locals'] + params, 'funcs': env['funcs'] }

    locals_string = ''
    for index in range(len(params), len(body_env['locals'])):
        type_ = body_env['locals'][index][1]
        locals_string += ('(local $' + str(index) + ' ' + type_ + ')\n    ')

    body = '\n    '.join(comp(func.body, body_env)[0])

    env['func_decs'] += ('\n  (func $' + func.name + ' ' + param_string + result_string + locals_string + body + return_string + ')')
    return ([], env)


def function_call(fc, env):
    """Call function
    Check if call is built-in print function.
    Otherwise, check if the function is defined, then check number of args and argument types (ints only for now)
    Generate code if everything checks out.
    """
    if fc.name == 'print':
        func_body = comp(fc.arguments[0], env)[0]
        env['return_type'] = None
        return (func_body + ['call $print'], env)
    else:
        fnames = list(env['funcs'])

        if fnames and fc.name in fnames:
            func = env['funcs'][fc.name]
            params = func['params']
            return_type = func['return_type']
            if len(fc.arguments) < len(params):
                die('call to ' + fc.name + ' does not have enough arguments', env['outpath'])
            elif len(fc.arguments) > len(params):
                die('call to ' + fc.name + ' has too many arguments', env['outpath'])
            else:
                args = []
                for param, arg in zip(params, fc.arguments):
                    arg, arg_env = comp(arg, env)
                    if param[1] == arg_env['return_type']:
                        args.extend(arg)
                    else:
                        die('type of argument to ' + param[0] + ' is ' + arg_env['return_type'] + ', but the parameter has type ' + param[1], env['outpath'])
            env['return_type'] = return_type
            return (args + ['call $' + fc.name ], env)
        else:
            die('function ' + fc.name + ' is not declared', env['outpath'])


# Blocks

def sequence(expressions, env):
    """Compile each expression in a sequence
    Update environment with as we go.
    """
    if expressions:
        code, next_env = comp(expressions[0], env)
        env['return_type'] = next_env['return_type']
        return (code + sequence(expressions[1:], next_env)[0], env)
    else:
        return ([], env)


def let(let, env):
    env_locals_len = len(env['locals'])
    let_env = env

    decls_code = []
    for decl in let.declarations:
        decl_body, let_env = comp(decl, let_env)
        if (decl_body != []):
            decls_code.extend(decl_body)

    in_code = []
    for expr in let.expressions:
        expr_body, let_env = comp(expr, let_env)
        in_code.extend(expr_body)

    let_body = ['  ' + op for op in decls_code + in_code]

    # add locals, but blot them out to put them out of scope
    env['locals'] = let_env['locals']
    for index in range(env_locals_len, len(let_env['locals'])):
        env['locals'][index] = ('', env['locals'][index][1])

    env['return_type'] = let_env['return_type']
    return (['block'] + let_body + ['end'], env)


# Structured control flow

def for_(for_, env):
    i_index = len(env['locals'])
    env['locals'].append( (for_.var, 'i32') )
    init = comp(for_.start, env)[0] + ['set_local $' + str(i_index)]

    t_index = len(env['locals'])
    env['locals'].append( (for_.var + '_t', 'i32') )
    termination = comp(for_.end, env)[0] + ['set_local $' + str(t_index)]

    for_body = comp(for_.body, env)[0]

    increment = ['get_local $' + str(i_index), 'i32.const 1', 'i32.add', 'set_local $' + str(i_index)]
    test = ['get_local $' + str(i_index), 'get_local $' + str(t_index), 'i32.le_s', 'br_if 0']

    loop_init = ['  ' + op for op in init + termination]
    loop_body = ['    ' + op for op in for_body + increment + test]

    if env['return_type'] is not None:
        die('expression in for cannot return a value', env['outpath'])

    return (['block'] + loop_init + ['  loop'] + loop_body + ['  end', 'end'], env)


def while_(while_, env):
    test = ['i32.const 1'] + comp(while_.condition, env)[0] + ['i32.sub', 'br_if 1']
    while_body = comp(while_.body, env)[0]
    loop_body = ['    ' + op for op in test + while_body + ['br 0']]
    if env['return_type'] is not None:
        die('expression in while cannot return a value', env['outpath'])
    return (['block', '  loop'] + loop_body + ['  end', 'end'], env)


def if_(if_, env):
    condition = comp(if_.condition, env)[0]

    body_if_true, if_env = comp(if_.body_if_true, env)
    true_return_type = if_env['return_type']
    if if_.body_if_false:
        body_if_false, if_env = comp(if_.body_if_false, env)
        false_return_type = if_env['return_type']
    else:
        body_if_false = ['nop']
        false_return_type = None

    if true_return_type == 'i32' and false_return_type == 'i32':
        if_string = 'if (result i32)'
    elif true_return_type == None and false_return_type == None:
        if_string = 'if'
    else:
        die('arms of an if-then-else expression must have the same type', env['outpath'])

    true_body = ['  ' + op for op in body_if_true]
    false_body = ['  ' + op for op in body_if_false]

    return(condition + [if_string] + true_body + ['else'] + false_body + ['end'], env)

# TODO: check if unsigned integer instructions are needed
emit = {
    IntegerValue: lambda intval, env: (['i32.const ' +  str(intval.integer)], set_int_return(env)),
    # StringValue: lambda strval, env: ([''], env),
    Add: lambda add, env: (comp(add.left, env)[0] + comp(add.right, env)[0] + ['i32.add'], set_int_return(env)),
    Subtract: lambda sub, env: (comp(sub.left, env)[0] + comp(sub.right, env)[0] + ['i32.sub'], set_int_return(env)),
    Multiply: lambda mul, env: (comp(mul.left, env)[0] + comp(mul.right, env)[0] + ['i32.mul'], set_int_return(env)),
    Divide: lambda div, env: (comp(div.left, env)[0] + comp(div.right, env)[0] + ['i32.div_s'], set_int_return(env)),
    Equals: lambda eq, env: (comp(eq.left, env)[0] + comp(eq.right, env)[0] + ['i32.eq'], set_int_return(env)),
    NotEquals: lambda ne, env: (comp(ne.left, env)[0] + comp(ne.right, env)[0] + ['i32.ne'], set_int_return(env)),
    LessThan: lambda lt, env: (comp(lt.left, env)[0] + comp(lt.right, env)[0] + ['i32.lt_s'], set_int_return(env)),
    GreaterThan: lambda gt, env: (comp(gt.left, env)[0] + comp(gt.right, env)[0] + ['i32.gt_s'], set_int_return(env)),
    LessThanOrEquals: lambda le, env: (comp(le.left, env)[0] + comp(le.right, env)[0] + ['i32.le_s'], set_int_return(env)),
    GreaterThanOrEquals: lambda ge, env: (comp(ge.left, env)[0] + comp(ge.right, env)[0] + ['i32.ge_s'], set_int_return(env)),
    And: lambda and_, env: (comp(and_.left, env)[0] + comp(and_.right, env)[0] + ['i32.and'], set_int_return(env)),
    Or: lambda or_, env: (comp(or_.left, env)[0] + comp(or_.right, env)[0] + ['i32.or'], set_int_return(env)),
    VariableDeclaration: lambda var, env: variable_declaration(var, env),
    Assign: lambda assn, env: assign(assn, env),
    LValue: lambda lval, env: lvalue(lval, env),
    TypeId: lambda typeid, env: type_id(typeid, env),
    FunctionDeclaration: lambda func, env: function_declaration(func, env),
    FunctionCall: lambda fc, env: function_call(fc, env),
    Sequence: lambda seq, env: sequence(seq.expressions, env),
    Let: lambda l, env: let(l, env),
    For: lambda f, env: for_(f, env),
    While: lambda w, env: while_(w, env),
    If: lambda i, env: if_(i, env)
}


# Compilation

def comp(ast, env):
    """Generate code from AST updating the environment as we go"""
    (code, next_env) = emit[ast.__class__](ast, env)
    return (code, next_env)


# TODO: keep types in a data structure
module = '(module)'
types = '''
  (type $t0 (func (param i32)))
  (type $t1 (func))'''
memory = '''
  (import "env" "memory" (memory $0 1))'''
imports = '''
  (import "env" "print" (func $print (type $t0)))'''
exports = '''
  (export "main" (func $main))'''
data = r'''
  (data 0 (offset (i32.const 4)) "\20\27\00\00")
'''


# def compile_main(ast):
def compile_main(ast, outpath):
    """Compile main function
    This function provides a wrapper for the program to allow it to be called by a main function.
    Module level code such function declarations and types are collected at this level,
    and code text is assembled here including imports, exports, and code to set up memory.
    """
    env = {
        'outpath': outpath,
        # types: [],
        'func_decs': '',
        # datatypes: {},
        'funcs': {},
        'locals': [],
        'return_type': None,
        'memory': False
    }
    main_body, main_env = comp(ast, env)
    locals_string = ''
    for index in range(0, len(main_env['locals'])):
        locals_string += '(local $' + str(index) + ' ' + main_env['locals'][index][1] + ')\n    '
    main_body_string = '\n    '.join(main_body)
    func_main = '\n  (func $main (type $t1)\n    ' + locals_string + main_body_string + ')'
    if env['memory']:
        return module[:-1] + types + memory + imports + env['func_decs'] + func_main + exports + data + module[-1:]
    else:
        return module[:-1] + types + imports + env['func_decs'] + func_main + exports + module[-1:]


if __name__ == '__main__':
    testpath = os.path.join("tests", sys.argv[1])
    with open(testpath, 'r') as tiger_file:
        start_time = time.time()
        tiger_source = tiger_file.read()
        ast = Parser(tiger_source).parse()
        # print(ast)
        outpath = testpath[:-4]
        module = compile_main(ast, outpath)
        outfile = open(outpath + '.wat', 'w')
        outfile.write(module)
        outfile.close()
        elapsed_time = format((time.time() - start_time)*1000.0, '#.3g')
        print(str(elapsed_time) + "ms")

