library package FPBCore {
	doc /* Core library for Functional Process Blocks (FPBs).
	     *
	     * A Functional Process Block is an action that is realized by an
	     * external service (in this demo: a Python function). A user-defined
	     * FPB specializes FunctionalProcessBlock and declares its own
	     * in/out parameters. A usage of such an FPB redefines the parameters
	     * to bind concrete values.
	     */

	private import ScalarValues::*;

	action def FunctionalProcessBlock {
		doc /* Base type of all Functional Process Blocks. Carries no
		     * parameters of its own; specializations add them.
		     */
	}

	metadata def ServiceBinding {
		doc /* Annotates an FPB definition with the external service that
		     * realizes it (binding approach 2: model-annotated binding).
		     */
		attribute lang : String;
		attribute module : String;
		attribute function : String;
	}

	metadata def ParameterBinding {
		doc /* Annotates an FPB parameter with the name of the corresponding
		     * parameter of the service function. For out parameters, the
		     * name refers to a key of the result returned by the service.
		     */
		attribute pythonName : String;
	}
}
