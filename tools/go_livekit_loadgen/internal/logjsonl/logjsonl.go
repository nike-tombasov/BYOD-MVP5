package logjsonl

import (
	"encoding/json"
	"os"
	"sync"
)

type Logger struct {
	mu  sync.Mutex
	f   *os.File
	enc *json.Encoder
}

func New(path string) (*Logger, error) {
	f, err := os.Create(path)
	if err != nil {
		return nil, err
	}
	return &Logger{f: f, enc: json.NewEncoder(f)}, nil
}
func (l *Logger) Event(v any)  { l.mu.Lock(); defer l.mu.Unlock(); _ = l.enc.Encode(v) }
func (l *Logger) Close() error { return l.f.Close() }
