#!/usr/bin/env python3

import sys

def test_rpy2_error_types():
    """Test to identify the specific error types that rpy2 raises."""
    try:
        import rpy2.robjects as robjects
        
        print("Initializing R session...")
        r = robjects.r
        
        # Test 1: Access a non-existent variable
        print("\nTest 1: Accessing a non-existent variable")
        try:
            result = r("non_existent_variable")
            print("Result:", result)
        except Exception as e:
            print(f"Error type: {type(e).__name__}")
            print(f"Error module: {e.__class__.__module__}")
            print(f"Error message: {str(e)}")
            print(f"Error class hierarchy: {', '.join(c.__name__ for c in e.__class__.__mro__)}")
        
        # Test 2: Syntax error
        print("\nTest 2: R syntax error")
        try:
            result = r("1 + ")
            print("Result:", result)
        except Exception as e:
            print(f"Error type: {type(e).__name__}")
            print(f"Error module: {e.__class__.__module__}")
            print(f"Error message: {str(e)}")
            print(f"Error class hierarchy: {', '.join(c.__name__ for c in e.__class__.__mro__)}")
        
        # Test 3: Division by zero
        print("\nTest 3: Division by zero")
        try:
            result = r("1 / 0")
            print("Result:", result)
        except Exception as e:
            print(f"Error type: {type(e).__name__}")
            print(f"Error module: {e.__class__.__module__}")
            print(f"Error message: {str(e)}")
            print(f"Error class hierarchy: {', '.join(c.__name__ for c in e.__class__.__mro__)}")
        else:
            print("Note: R might handle division by zero differently (not as an error)")
            print("Result:", result)
        
        # Test 4: Function error
        print("\nTest 4: Error in a function")
        try:
            result = r("stop('This is a deliberate error from R')")
            print("Result:", result)
        except Exception as e:
            print(f"Error type: {type(e).__name__}")
            print(f"Error module: {e.__class__.__module__}")
            print(f"Error message: {str(e)}")
            print(f"Error class hierarchy: {', '.join(c.__name__ for c in e.__class__.__mro__)}")
            
    except ImportError:
        print("rpy2 is not installed")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(test_rpy2_error_types()) 