for i in tests/*.tig
do
    FILE=$(echo $i | cut -c7-)
    echo "compile $FILE"
    python compiler.py $FILE
done

for i in tests/*.wat
do
    NAME=${i::-4}
    WASM=".wasm"
    echo "convert $i"
    ~/langs/wasm-spec/interpreter/wasm -d $i -o $NAME$WASM
done

